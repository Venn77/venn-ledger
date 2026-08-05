Venn Ledger - Linux / Steam Deck Setup

To use the AI Import features, you must have Ollama running locally.
Please follow the instructions for your specific operating system below.

-----------------------------------------------------------
OPTION A: STANDARD LINUX (Ubuntu, Mint, Fedora, Arch, etc.)
-----------------------------------------------------------
1. Open your Terminal and run the official install script:
   curl -fsSL https://ollama.com/install.sh | sh

2. Download the required AI model:
   ollama pull mistral:7b

3. Run Venn Ledger!


-----------------------------------------------------------
OPTION B: STEAM DECK / STEAMOS
-----------------------------------------------------------
Because SteamOS is read-only, the standard installer above will fail.

1. Open Konsole (in Desktop Mode) and run this to download the engine:
   curl -L https://ollama.com/download/ollama-linux-amd64 -o ~/.local/bin/ollama && chmod +x ~/.local/bin/ollama

2. Download the required AI model:
   ~/.local/bin/ollama pull mistral:7b

3. Run Venn Ledger!
(Note: You may need to manually run '~/.local/bin/ollama serve &' in Konsole after a reboot to start the engine).