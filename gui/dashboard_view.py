import customtkinter as ctk
from typing import Literal, Any
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.ticker as ticker
import datetime
import mplcursors
from database.models import Expense, Gain


class DashboardView(ctk.CTkFrame):
    def __init__(self, parent, manager, db_session):
        super().__init__(parent, fg_color="transparent")
        self.app = parent
        self.manager = manager
        self.db_session = db_session

        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.pack(fill="x", pady=(0, 10))

        self.header = ctk.CTkLabel(self.header_frame, text="Financial Dashboard", font=("JetBrains Mono", 22, "bold"))
        self.header.pack(side="left")

        self.range_var = ctk.StringVar(value="6 Months")
        self.range_selector = ctk.CTkSegmentedButton(
            self.header_frame,
            values=["1 Month", "3 Months", "6 Months", "12 Months", "3 Years", "5 Years"],
            variable=self.range_var,
            command=self._on_range_change,
            selected_color="#1f538d",
            selected_hover_color="#14375e"
        )
        self.range_selector.pack(side="right")

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True)

        plt.style.use('dark_background')

        plt.rcParams['font.family'] = 'sans-serif'
        plt.rcParams['font.sans-serif'] = ['JetBrains Mono', 'Segoe UI']

        self.bg_color = '#2b2b2b'
        # noinspection PyTypeChecker
        self.after(50, self.build_dashboard)

    def _on_range_change(self, _selected_value):
        for widget in self.scroll.winfo_children():
            widget.destroy()
        plt.close('all')
        self.build_dashboard()

    def build_dashboard(self):
        range_str = self.range_var.get()

        cf_labels, incomes, expenses, nw_labels, net_worths, start_date = self._get_historical_data(range_str)
        cat_labels, cat_values, other_breakdown = self._get_category_data(start_date)

        top_frame = ctk.CTkFrame(self.scroll, fg_color=self.bg_color, corner_radius=8)
        top_frame.pack(fill="x", pady=(0, 15), padx=5)
        self._draw_cashflow(top_frame, cf_labels, incomes, expenses, range_str)

        bottom_frame = ctk.CTkFrame(self.scroll, fg_color="transparent")
        bottom_frame.pack(fill="both", expand=True, pady=5)
        bottom_frame.grid_columnconfigure((0, 1), weight=1)

        bl_frame = ctk.CTkFrame(bottom_frame, fg_color=self.bg_color, corner_radius=8)
        bl_frame.grid(row=0, column=0, sticky="nsew", padx=(5, 10))
        self._draw_donut(bl_frame, cat_labels, cat_values, other_breakdown)

        br_frame = ctk.CTkFrame(bottom_frame, fg_color=self.bg_color, corner_radius=8)
        br_frame.grid(row=0, column=1, sticky="nsew", padx=(10, 5))
        self._draw_networth(br_frame, nw_labels, net_worths)

    def _get_historical_data(self, range_str):
        today = datetime.date.today()

        if range_str == "1 Month":
            start_date = datetime.datetime.combine(today - datetime.timedelta(days=30), datetime.time.min)
            all_gains = self.db_session.query(Gain).filter(Gain.timestamp >= start_date).all()
            all_expenses = self.db_session.query(Expense).filter(Expense.timestamp >= start_date).all()

            inc_sum = sum(g.converted_amount for g in all_gains)
            exp_sum = sum(e.converted_amount for e in all_expenses)

            current_nw = self.manager.get_net_worth()
            past_nw = current_nw - (inc_sum - exp_sum)

            return ["Last 30 Days"], [inc_sum], [exp_sum], ["30 Days Ago", "Today"], [past_nw, current_nw], start_date

        elif "Year" in range_str:
            years_back = int(range_str.split()[0])
            start_year = today.year - (years_back - 1)
            start_date = datetime.datetime(start_year, 1, 1)

            labels = [str(y) for y in range(start_year, today.year + 1)]
            incomes = [0] * years_back
            expenses = [0] * years_back

            all_gains = self.db_session.query(Gain).filter(Gain.timestamp >= start_date).all()
            all_expenses = self.db_session.query(Expense).filter(Expense.timestamp >= start_date).all()

            for g in all_gains:
                idx = g.timestamp.year - start_year
                incomes[idx] += g.converted_amount

            for e in all_expenses:
                idx = e.timestamp.year - start_year
                expenses[idx] += e.converted_amount

            current_nw = self.manager.get_net_worth()
            net_worths = [0] * years_back
            temp_nw = current_nw

            for i in range(years_back - 1, -1, -1):
                net_worths[i] = temp_nw
                temp_nw -= (incomes[i] - expenses[i])

            return labels, incomes, expenses, labels, net_worths, start_date

        else:
            months_back = int(range_str.split()[0])
            months = []
            for i in range(months_back - 1, -1, -1):
                m = today.month - i
                y = today.year
                while m <= 0:
                    m += 12
                    y -= 1
                months.append((y, m))

            label_format = '%b' if months_back <= 6 else '%b\n%y'
            labels = [datetime.date(y, m, 1).strftime(label_format) for y, m in months]

            incomes = [0] * months_back
            expenses = [0] * months_back

            start_date = datetime.datetime(months[0][0], months[0][1], 1)

            all_gains = self.db_session.query(Gain).filter(Gain.timestamp >= start_date).all()
            all_expenses = self.db_session.query(Expense).filter(Expense.timestamp >= start_date).all()

            for g in all_gains:
                idx = months.index((g.timestamp.year, g.timestamp.month))
                incomes[idx] += g.converted_amount

            for e in all_expenses:
                idx = months.index((e.timestamp.year, e.timestamp.month))
                expenses[idx] += e.converted_amount

            current_nw = self.manager.get_net_worth()
            net_worths = [0] * months_back
            temp_nw = current_nw

            for i in range(months_back - 1, -1, -1):
                net_worths[i] = temp_nw
                temp_nw -= (incomes[i] - expenses[i])

            return labels, incomes, expenses, labels, net_worths, start_date

    def _get_category_data(self, start_date):
        expenses = self.db_session.query(Expense).filter(Expense.timestamp >= start_date).all()

        cat_dict = {}
        for e in expenses:
            c_name = e.category.name if e.category else "Uncategorized"
            cat_dict[c_name] = cat_dict.get(c_name, 0) + e.converted_amount

        sorted_cats = sorted(cat_dict.items(), key=lambda x: x[1], reverse=True)

        labels = [k for k, v in sorted_cats[:10]]
        values = [v for k, v in sorted_cats[:10]]

        other_breakdown = []
        if len(sorted_cats) > 10:
            labels.append("Other")
            values.append(sum(v for k, v in sorted_cats[10:]))
            other_breakdown = sorted_cats[10:20]

        return labels, values, other_breakdown

    def _draw_cashflow(self, parent_frame, labels, incomes, expenses, range_str):
        title = "30-Day Cash Flow" if range_str == "1 Month" else f"Cash Flow ({range_str})"
        ctk.CTkLabel(parent_frame, text=title, font=("JetBrains Mono", 14, "bold")).pack(pady=(10, 0))

        fig, ax = plt.subplots(figsize=(10, 3), facecolor=self.bg_color)
        ax.set_facecolor(self.bg_color)

        x = range(len(labels))
        width = 0.35

        max_val = float(max(max(incomes + [0]), max(expenses + [0])))
        min_h = max_val * 0.015 if max_val > 0 else 0

        vis_incomes = [max(val, min_h) if val > 0 else 0 for val in incomes]
        vis_expenses = [max(val, min_h) if val > 0 else 0 for val in expenses]

        bars_in = ax.bar([i - width / 2 for i in x], vis_incomes, width, label='Income', color='#4CD964')
        bars_out = ax.bar([i + width / 2 for i in x], vis_expenses, width, label='Expenses', color='#FF6B6B')

        ax.set_xticks(x)
        ax.set_xticklabels(labels, fontsize=9 if len(labels) > 6 else 10)
        ax.legend(frameon=False)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.grid(axis='y', alpha=0.2)

        ax.yaxis.set_major_formatter(ticker.StrMethodFormatter('{x:,.0f}'))

        fig.tight_layout()

        cursor = mplcursors.cursor([bars_in, bars_out], hover=True)

        @cursor.connect("add")
        def on_add(sel):
            idx = int(round(float(sel.index)))

            if sel.artist == bars_in:
                real_val = incomes[idx]
            else:
                real_val = expenses[idx]

            sel.annotation.set_text(f"{self.manager.base_currency_symbol} {real_val:,.{self.manager.base_currency_decimals}f}")
            sel.annotation.get_bbox_patch().set(fc="#1f1f1f", ec="white", alpha=0.9, boxstyle="round,pad=0.3")
            sel.annotation.arrow_patch.set(color="white")

        canvas = FigureCanvasTkAgg(fig, master=parent_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=(0, 10))

    def _draw_donut(self, parent_frame, labels, values, other_breakdown):
        ctk.CTkLabel(parent_frame, text="Expense Breakdown", font=("JetBrains Mono", 14, "bold")).pack(pady=(10, 0))

        fig, ax = plt.subplots(figsize=(4, 3), facecolor=self.bg_color)

        if not values:
            ax.text(0.5, 0.5, 'No Data Yet', ha='center', va='center', color='gray')
            ax.axis('off')
            canvas = FigureCanvasTkAgg(fig, master=parent_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=(0, 10))
            return

        base_colors = [
            '#FF6B6B', '#FF9F0A', '#FFD60A', '#32ADE6', '#AF52DE',
            '#FF375F', '#5E5CE6', '#BF5AF2', '#64D2FF', '#30D158',
            '#8E8E93'
        ]

        slice_colors = base_colors[:len(values)]
        if labels[-1] == "Other":
            slice_colors[-1] = '#8E8E93'

        wedges, texts, autotexts = ax.pie(values, labels=labels, autopct='%1.1f%%',
                                          startangle=90, colors=slice_colors, textprops=dict(color="w", fontsize=8))

        center_circle = plt.Circle((0, 0), 0.70, fc=self.bg_color)
        fig.gca().add_artist(center_circle)
        ax.axis('equal')

        fig.tight_layout()

        canvas = FigureCanvasTkAgg(fig, master=parent_frame)

        annot = ax.annotate("", xy=(0, 0), xytext=(20, 20), textcoords="offset points",
                            bbox=dict(boxstyle="round,pad=0.3", fc="#1f1f1f", ec="white", alpha=0.9),
                            color="white", zorder=5)
        annot.set_visible(False)

        def hover(event: Any):
            if event.inaxes == ax and event.xdata is not None and event.ydata is not None:
                for i, wedge in enumerate(wedges):
                    cont, ind = wedge.contains(event)
                    if cont:
                        x_val = float(event.xdata)
                        y_val = float(event.ydata)

                        annot.xy = (x_val, y_val)

                        x_offset = -20 if x_val > 0 else 20
                        ha: Literal["left", "right"] = 'right' if x_val > 0 else 'left'

                        y_offset = -20 if y_val > 0 else 20
                        va: Literal["top", "bottom"] = 'top' if y_val > 0 else 'bottom'

                        annot.set_position((x_offset, y_offset))
                        annot.set_horizontalalignment(ha)
                        annot.set_verticalalignment(va)

                        total = sum(values)
                        pct = (values[i] / total) * 100 if total > 0 else 0

                        text = f"{labels[i]}\n{self.manager.base_currency_symbol} {values[i]:,.{self.manager.base_currency_decimals}f} ({pct:.1f}%)"

                        if labels[i] == "Other" and other_breakdown:
                            breakdown_str = "\n".join([f"• {k}: {self.manager.base_currency_symbol}{v:,.0f}" for k, v in other_breakdown])
                            text += f"\n\nIncludes:\n{breakdown_str}"
                            if len(other_breakdown) == 10:
                                text += "\n..."

                        annot.set_text(text)
                        bbox = annot.get_bbox_patch()
                        if bbox:
                            bbox.set_edgecolor(slice_colors[i])
                        annot.set_visible(True)
                        canvas.draw_idle()
                        return

            if annot.get_visible():
                annot.set_visible(False)
                canvas.draw_idle()

        canvas.mpl_connect("motion_notify_event", hover)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=(0, 10))

    def _draw_networth(self, parent_frame, labels, net_worths):
        ctk.CTkLabel(parent_frame, text="Net Worth Trend", font=("JetBrains Mono", 14, "bold")).pack(pady=(10, 0))

        fig, ax = plt.subplots(figsize=(4, 3), facecolor=self.bg_color)
        ax.set_facecolor(self.bg_color)

        line, = ax.plot(labels, net_worths, marker='o', color='#5AC8FA', linewidth=2, markersize=6)
        ax.fill_between(labels, net_worths, color='#5AC8FA', alpha=0.1)

        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.grid(axis='y', alpha=0.2)

        ax.yaxis.set_major_formatter(ticker.StrMethodFormatter('{x:,.0f}'))

        min_nw = float(min(net_worths))
        if min_nw > 0:
            ax.set_ylim(bottom=min_nw * 0.95)

        ax.tick_params(axis='x', labelsize=9 if len(labels) > 6 else 10)

        fig.tight_layout()

        cursor = mplcursors.cursor(line, hover=True)

        @cursor.connect("add")
        def on_add(sel):
            idx = int(round(float(sel.index)))
            month_label = labels[idx]
            val = net_worths[idx]

            sel.annotation.set_text(f"{month_label}\n{self.manager.base_currency_symbol} {val:,.{self.manager.base_currency_decimals}f}")
            sel.annotation.xy = (idx, val)
            sel.annotation.get_bbox_patch().set(fc="#1f1f1f", ec="#5AC8FA", alpha=0.9, boxstyle="round,pad=0.3")

        canvas = FigureCanvasTkAgg(fig, master=parent_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=(0, 10))

    def refresh_view(self):
        """Called automatically when switching back to this tab.
        Clears out the old charts and redraws them with fresh data."""
        for widget in self.scroll.winfo_children():
            widget.destroy()

        plt.close('all')

        self.build_dashboard()
