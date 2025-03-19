import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import subprocess

from pdf_generator import create_pdf, load_card_list_from_text
import mec_prof  # Modulo per la generazione del contenuto delle meccaniche


def open_pdf(filepath):
    try:
        if sys.platform.startswith('darwin'):
            subprocess.run(['open', filepath])
        elif sys.platform.startswith('win'):
            os.startfile(filepath)
        elif sys.platform.startswith('linux'):
            subprocess.run(['xdg-open', filepath])
    except Exception as e:
        print(f"Errore nell'apertura del PDF: {e}")


class PDFGeneratorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Magic Card Info Generator")
        self.geometry("625x850")
        self.resizable(True, True)
        self.cancel_requested = False  # Flag per la cancellazione del processo
        style = ttk.Style(self)
        style.theme_use("clam")
        self.create_widgets()
        self.center_window(self)  # Centra la finestra principale

    def center_window(self, window):
        window.update_idletasks()
        w = window.winfo_width()
        h = window.winfo_height()
        ws = window.winfo_screenwidth()
        hs = window.winfo_screenheight()
        x = (ws // 2) - (w // 2)
        y = (hs // 2) - (h // 2)
        window.geometry(f"+{x}+{y}")

    def create_widgets(self):
        main_frame = ttk.Frame(self, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Liste salvate e nome della lista
        ttk.Button(main_frame, text="Liste salvate", command=self.open_saved_list).grid(
            row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 10)
        )
        ttk.Label(main_frame, text="Nome della lista:").grid(
            row=1, column=0, sticky=tk.W, pady=(0, 5)
        )
        self.list_name = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.list_name, width=50).grid(
            row=1, column=1, sticky=tk.W, pady=(0, 5)
        )

        # Elenco delle carte
        ttk.Label(main_frame, text="Incolla qui l'elenco delle carte (una per riga):").grid(
            row=2, column=0, columnspan=2, sticky=tk.W, pady=(10, 5)
        )
        self.text_input = scrolledtext.ScrolledText(main_frame, width=70, height=15)
        self.text_input.grid(row=3, column=0, columnspan=2, pady=5)
        example_cards = "1 Sauron, the Dark Lord\n2 Swamp\nArcane Denial\n1 Anger"
        self.text_input.insert(tk.END, example_cards)

        # Bottone "Spiega meccaniche" posizionato subito dopo l'elenco delle carte
        ttk.Button(main_frame, text="Spiegami le meccaniche delle carte", command=self.show_mechanics).grid(
            row=4, column=0, columnspan=2, sticky=tk.W, pady=(10, 10)
        )

        # Sezione per la generazione PDF (spostata sotto il bottone "Spiega meccaniche")
        gen_frame = ttk.LabelFrame(main_frame, text="Generazione", padding=10)
        gen_frame.grid(row=5, column=0, columnspan=2, sticky=tk.EW, pady=(10, 5))
        self.gen_option = tk.StringVar(value="both")
        ttk.Radiobutton(gen_frame, text="Solo Suggerimenti", variable=self.gen_option, value="suggestions").grid(
            row=0, column=0, sticky=tk.W, pady=2
        )
        ttk.Radiobutton(gen_frame, text="Solo Elenco Carte", variable=self.gen_option, value="cards").grid(
            row=1, column=0, sticky=tk.W, pady=2
        )
        ttk.Radiobutton(gen_frame, text="Entrambe", variable=self.gen_option, value="both").grid(
            row=2, column=0, sticky=tk.W, pady=2
        )

        # Opzioni relative alle lands
        lands_frame = ttk.LabelFrame(main_frame, text="Lands", padding=10)
        lands_frame.grid(row=6, column=0, columnspan=2, sticky=tk.EW, pady=(0, 5))
        self.lands_exclusion = tk.StringVar(value="none")
        ttk.Radiobutton(lands_frame, text="Nessuna esclusione", variable=self.lands_exclusion, value="none").grid(
            row=0, column=0, sticky=tk.W, pady=2
        )
        ttk.Radiobutton(lands_frame, text="Escludi solo Basic lands", variable=self.lands_exclusion,
                        value="basic").grid(
            row=1, column=0, sticky=tk.W, pady=2
        )
        ttk.Radiobutton(lands_frame, text="Escludi tutte le Lands", variable=self.lands_exclusion, value="all").grid(
            row=2, column=0, sticky=tk.W, pady=2
        )

        # Opzioni per le versioni alternative
        versions_frame = ttk.LabelFrame(main_frame, text="Versioni alternative", padding=10)
        versions_frame.grid(row=7, column=0, columnspan=2, sticky=tk.EW, pady=(0, 5))
        self.version_exclusion = tk.StringVar(value="include")
        ttk.Radiobutton(versions_frame, text="Includi tutte le versioni", variable=self.version_exclusion,
                        value="include").grid(
            row=0, column=0, sticky=tk.W, pady=2
        )
        ttk.Radiobutton(versions_frame, text="Mostra solo la versione principale", variable=self.version_exclusion,
                        value="exclude").grid(
            row=1, column=0, sticky=tk.W, pady=2
        )

        # Bottoni in basso: Genera PDF
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=8, column=0, columnspan=2, pady=(10, 0))
        ttk.Button(button_frame, text="Genera PDF", command=self.start_process).grid(row=0, column=0, padx=5)

    def open_saved_list(self):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        lista_dir = os.path.join(script_dir, "liste")
        if not os.path.exists(lista_dir):
            messagebox.showerror("Errore", "La cartella 'liste' non esiste.")
            return
        files = [f for f in os.listdir(lista_dir) if f.lower().endswith('.pdf')]
        if not files:
            messagebox.showinfo("Nessuna lista", "Non ci sono liste salvate.")
            return
        popup = tk.Toplevel(self)
        popup.title("Seleziona lista salvata")
        popup.geometry("300x200")
        self.center_window(popup)
        popup.transient(self)
        popup.grab_set()
        popup.focus_set()
        # Imposto un font standard per evitare sottolineature
        ttk.Label(popup, text="Seleziona la lista da aprire:", font=("TkDefaultFont", 10)).pack(pady=10)
        listbox = tk.Listbox(popup, font=("TkDefaultFont", 10))
        listbox.pack(fill=tk.BOTH, expand=True, padx=10)
        for file in files:
            listbox.insert(tk.END, file)

        def on_select():
            selection = listbox.curselection()
            if selection:
                selected_file = listbox.get(selection[0])
                file_path = os.path.join(lista_dir, selected_file)
                open_pdf(file_path)
                popup.destroy()

        ttk.Button(popup, text="Apri", command=on_select).pack(pady=10)

    def start_process(self):
        list_name = self.list_name.get().strip()
        if not list_name:
            messagebox.showerror("Errore", "Inserisci il nome della lista.")
            return
        text = self.text_input.get("1.0", tk.END)
        pdf_cards, ai_cards, card_counts = load_card_list_from_text(text)
        if not pdf_cards:
            messagebox.showerror("Errore", "Inserisci almeno una carta nell'elenco.")
            return

        script_dir = os.path.dirname(os.path.abspath(__file__))
        lista_dir = os.path.join(script_dir, "liste")
        os.makedirs(lista_dir, exist_ok=True)
        output_path = os.path.join(lista_dir, f"{list_name}.pdf")

        # Imposto la flag di cancellazione a False
        self.cancel_requested = False

        # Crea il pop-up di avanzamento (modal)
        self.progress_popup = tk.Toplevel(self)
        self.progress_popup.title("Download in corso...")
        self.progress_popup.geometry("300x100")
        self.center_window(self.progress_popup)
        self.progress_popup.protocol("WM_DELETE_WINDOW", self.cancel_process)
        self.progress_popup.transient(self)
        self.progress_popup.grab_set()
        self.progress_popup.focus_set()
        # Modifica del testo interno come richiesto
        self.popup_label = ttk.Label(self.progress_popup, text="...attendi qualche istante per favore\n mentre faccio una magia..")
        self.popup_label.pack(pady=20)

        # Avvia il thread per la generazione del PDF
        gen_mode = self.gen_option.get()
        thread = threading.Thread(
            target=self.process_pdf,
            args=(pdf_cards, ai_cards, card_counts, output_path, gen_mode,
                  self.lands_exclusion.get(), self.version_exclusion.get())
        )
        thread.start()

    def cancel_process(self):
        # Quando l'utente clicca sulla X del pop-up, impostiamo la flag e chiudiamo il pop-up
        self.cancel_requested = True
        if hasattr(self, "progress_popup") and self.progress_popup.winfo_exists():
            self.progress_popup.destroy()
        messagebox.showinfo("Annullato", "Operazione annullata dall'utente.")

    def update_progress(self, processed, total):
        # Se l'utente ha richiesto la cancellazione, interrompiamo il processo
        if self.cancel_requested:
            raise Exception("Operazione annullata dall'utente")
        percent = int((processed / total) * 100)
        self.progress_popup.after(0, lambda: self.popup_label.config(text=f"...attendi qualche istante per favore\n mentre faccio una magia... {percent}%"))

    def process_pdf(self, pdf_cards, ai_cards, card_counts, output_path, gen_mode, lands_exclusion, version_exclusion):
        try:
            # Supponiamo che create_pdf richiami periodicamente progress_callback
            create_pdf(pdf_cards, ai_cards, card_counts, output_path, generation_mode=gen_mode,
                       lands_exclusion=lands_exclusion, version_exclusion=version_exclusion,
                       progress_callback=self.update_progress)
            # Se il processo non è stato annullato, chiudiamo il pop-up e mostriamo il messaggio di successo
            if not self.cancel_requested:
                self.progress_popup.after(0, self.progress_popup.destroy)
                messagebox.showinfo("Fatto", f"PDF creato correttamente:\n{output_path}")
                open_pdf(output_path)
        except Exception as e:
            # In caso di errore o annullamento, chiudiamo il pop-up e mostriamo l'errore
            if hasattr(self, "progress_popup") and self.progress_popup.winfo_exists():
                self.progress_popup.after(0, self.progress_popup.destroy)
            messagebox.showerror("Errore", f"Si è verificato un errore: {e}")

    def show_mechanics(self):
        # Ottieni il contenuto strutturato dal modulo mec_prof
        results = mec_prof.generate_mechanics_content(self.text_input)

        # Crea la finestra per mostrare il contenuto con uno stile migliorato
        mech_window = tk.Toplevel(self)
        mech_window.title("Spiegazione Meccaniche")
        mech_window.geometry("600x400")
        self.center_window(mech_window)
        self.grab_set()
        self.focus_set()
        mech_window.configure(bg="#f0f0f0")  # Sfondo chiaro

        # Creazione di un frame interno con padding per una migliore estetica
        frame = ttk.Frame(mech_window, padding="10 10 10 10")
        frame.pack(fill=tk.BOTH, expand=True)

        st = scrolledtext.ScrolledText(frame, width=80, height=20, font=("Helvetica", 10))
        st.pack(fill=tk.BOTH, expand=True)
        st.tag_configure("bold", font=("Helvetica", 10, "bold"))

        # Inserisci i dati per ogni carta con formattazione migliorata
        for item in results:
            st.insert(tk.END, "Carta:\n", "bold")
            st.insert(tk.END, f"{item['card']}\n\n")

            st.insert(tk.END, "Effetto:\n", "bold")
            st.insert(tk.END, f"{item['oracle']}\n\n")

            st.insert(tk.END, "Meccaniche individuate:\n", "bold")
            if item['mechs']:
                st.insert(tk.END, "\n\n".join(item['mechs']) + "\n")
            else:
                st.insert(tk.END, "Nessuna meccanica individuata.\n")

            st.insert(tk.END, "-" * 50 + "\n\n")

        st.configure(state="disabled")


if __name__ == "__main__":
    app = PDFGeneratorApp()
    app.mainloop()
