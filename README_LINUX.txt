Venn Ledger - Linux / Steam Deck Setup

To use the AI Import features, you must have Ollama installed locally.
Please follow the instructions for your specific operating system below.

-----------------------------------------------------------
OPTION A: STANDARD LINUX (Ubuntu, Mint, Fedora, Arch, etc.)
-----------------------------------------------------------
1. Open your Terminal and run the official install script:
   curl -fsSL https://ollama.com/install.sh | sh

2. Download the required AI model:
   ollama pull mistral:7b

3. Run Venn Ledger! (The app will automatically manage the AI engine).


-----------------------------------------------------------
OPTION B: STEAM DECK / STEAMOS
-----------------------------------------------------------
Because SteamOS is read-only, the standard installer above will fail.

1. Open Konsole (in Desktop Mode) and download the standalone binaries:
   mkdir -p ~/.local && curl -L https://ollama.com/download/ollama-linux-amd64.tar.zst | tar -x --zstd -C ~/.local

2. Open a SECOND Konsole tab (leaving the first one open).
   In Tab 1, start the engine temporarily:
   OLLAMA_IGPU_ENABLE=1 ~/.local/bin/ollama serve

   In Tab 2, download the required AI model:
   ~/.local/bin/ollama pull mistral:7b

3. Once the download finishes, you can close both Konsole tabs!

4. Run Venn Ledger!
(Note: You never need to run these commands again. Venn Ledger will silently boot up the AI engine in the background whenever you open the app, and close it when you exit).