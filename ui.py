import tkinter as tk
from tkinter import ttk, filedialog, messagebox, Canvas, Toplevel
from PIL import Image, ImageTk
from collections import OrderedDict
import time
from concurrent.futures import ThreadPoolExecutor
import sys
import os
import threading

# 语言文件字典
LANGUAGES = {
    "zh_CN": "zh_CN.lang",
    "en_US": "en_US.lang"
}
CURRENT_LANGUAGE = "zh_CN"

def resource_path(relative_path):
    """ 获取资源文件的绝对路径 """
    if hasattr(sys, '_MEIPASS'):
        # 打包后运行
        return os.path.join(sys._MEIPASS, relative_path)
    # 开发环境运行
    return os.path.join(os.path.abspath("."), relative_path)

def load_language(lang):
    lang_dict = {}
    lang_file = LANGUAGES.get(lang)
    if lang_file:
        # 获取语言文件的实际路径
        lang_file_path = resource_path(lang_file)
        if os.path.exists(lang_file_path):
            with open(lang_file_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        key, value = line.split("=", 1)
                        lang_dict[key.strip()] = value.strip()
    return lang_dict


class ImageDeduplicatorUI:
    def __init__(self, root, hash_calculator, duplicate_analyzer):
        self.root = root
        self.root.title(self._get_lang_text("TITLE", "Default Title"))
        self.root.geometry("1000x800")
        self.root.minsize(800, 600)

        self.style = ttk.Style()
        self.style.theme_use("default")
        self.style.configure("TButton", padding=6)
        self.style.configure("TFrame", background="#f0f0f0")
        self.style.configure("TLabel", background="#f0f0f0")
        self.style.configure("TLabelframe", background="#f0f0f0")
        self.style.configure("TLabelframe.Label", background="#f0f0f0")

        self.image_cache = OrderedDict()
        self.MAX_CACHE_SIZE = 100
        self.hash_calculator = hash_calculator
        self.duplicate_analyzer = duplicate_analyzer

        self.create_main_layout()
        self._update_check_button_state()

    def create_main_layout(self):
        # 顶部框架，包含语言切换按钮和操作按钮
        top_frame = ttk.Frame(self.root, padding=10)
        top_frame.pack(fill=tk.X, side=tk.TOP)

        self.create_language_switcher(top_frame)
        self.create_action_buttons(top_frame)

        # 中间框架，包含进度条和日志显示
        middle_frame = ttk.Frame(self.root, padding=10)
        middle_frame.pack(fill=tk.X, side=tk.TOP)

        self.create_progress_bar(middle_frame)
        self.create_log_display(middle_frame)

        # 底部框架，包含结果显示区域
        bottom_frame = ttk.Frame(self.root, padding=10)
        bottom_frame.pack(fill=tk.BOTH, expand=True, side=tk.TOP)

        self.create_result_display(bottom_frame)

    def create_language_switcher(self, parent):
        lang_frame = ttk.Frame(parent)
        lang_frame.pack(side=tk.RIGHT)

        self.lang_btn = ttk.Button(
            lang_frame,
            text="Switch to English" if CURRENT_LANGUAGE == "zh_CN" else "切换到中文",
            command=self.switch_language
        )
        self.lang_btn.pack(side=tk.RIGHT, padx=5)

    def create_action_buttons(self, parent):
        button_frame = ttk.Frame(parent)
        button_frame.pack(side=tk.LEFT)

        self.select_btn = ttk.Button(
            button_frame,
            text=self._get_lang_text("SELECT_BTN_TEXT", "Default select folder button text"),
            command=self.start_hash_calculation
        )
        self.select_btn.pack(side=tk.LEFT, padx=5)

        self.check_btn = ttk.Button(
            button_frame,
            text=self._get_lang_text("CHECK_BTN_TEXT", "Default check hashes button text"),
            command=self.start_check_duplicate_hashes,
            state=tk.DISABLED
        )
        self.check_btn.pack(side=tk.LEFT, padx=5)

    def create_progress_bar(self, parent):
        progress_frame = ttk.Frame(parent)
        progress_frame.pack(fill=tk.X, pady=5)

        self.progress_bar = ttk.Progressbar(
            progress_frame,
            orient=tk.HORIZONTAL,
            mode='determinate'
        )
        self.progress_bar.pack(fill=tk.X, expand=True, padx=5)

    def create_log_display(self, parent):
        log_frame = ttk.Frame(parent)
        log_frame.pack(fill=tk.X, pady=5)

        self.log_text = tk.Text(log_frame, wrap=tk.WORD, height=5)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def create_result_display(self, parent):
        result_frame = ttk.Frame(parent)
        result_frame.pack(fill=tk.BOTH, expand=True)

        v_scrollbar = ttk.Scrollbar(result_frame, orient=tk.VERTICAL)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        h_scrollbar = ttk.Scrollbar(result_frame, orient=tk.HORIZONTAL)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)

        self.canvas = Canvas(result_frame, yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        self.result_frame = ttk.Frame(self.canvas)
        self.canvas.create_window((0, 0), window=self.result_frame, anchor=tk.NW)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        v_scrollbar.config(command=self.canvas.yview)
        h_scrollbar.config(command=self.canvas.xview)

        self.result_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        result_frame.bind_all("<MouseWheel>", self._on_mousewheel)

    def start_hash_calculation(self):
        folder_path = filedialog.askdirectory()
        if folder_path:
            if self.hash_calculator.has_existing_hashes():
                result = messagebox.askyesno(
                    self._get_lang_text("MSG_COMPLETE", "Default completion message"),
                    self._get_lang_text("MSG_REGENERATE_HASH", "Default recalculate message")
                )
                if result:
                    self._toggle_buttons(False)
                    self.show_progress()
                    threading.Thread(
                        target=self.hash_calculator.calculate_hashes,
                        args=(folder_path, self._update_progress, self._on_hash_calculation_complete),
                        daemon=True
                    ).start()
                else:
                    self.check_btn.config(state=tk.NORMAL)
            else:
                self._toggle_buttons(False)
                self.show_progress()
                threading.Thread(
                    target=self.hash_calculator.calculate_hashes,
                    args=(folder_path, self._update_progress, self._on_hash_calculation_complete),
                    daemon=True
                ).start()
        else:
            self.log(self._get_lang_text("LOG_NO_FOLDER_SELECTED", "Default no folder selected message"))

    def start_check_duplicate_hashes(self):
        if not self.hash_calculator.has_existing_hashes():
            messagebox.showerror("😣Error😣", self._get_lang_text("MSG_CHECK_NEEDED", "Default need to calculate hashes message"))
            return
        self._toggle_buttons(False)
        threading.Thread(
            target=self.duplicate_analyzer.find_duplicates,
            args=(self._on_duplicate_check_complete,),
            daemon=True
        ).start()

    def _on_hash_calculation_complete(self, success):
        self.root.after(0, lambda: [
            self._toggle_buttons(True),
            self.progress_bar.config(value=0),
            messagebox.showinfo(self._get_lang_text("MSG_COMPLETE", "Default completion message"),
                                f"Results have been saved to {self.hash_calculator.result_file_path}!"),
            self.check_btn.config(state=tk.NORMAL),
            self.start_check_duplicate_hashes()
        ])

    def _on_duplicate_check_complete(self, duplicate_groups, suspicious_groups, all_image_hashes):
        self.root.after(0, lambda: [
            self.clear_result_frame(),
            self._toggle_buttons(True)
        ])
        if duplicate_groups or suspicious_groups:
            self.root.after(0, lambda: self.show_duplicates(duplicate_groups, suspicious_groups, all_image_hashes))
        else:
            self.root.after(0, lambda: messagebox.showinfo(
                self._get_lang_text("MSG_NO_DUPLICATES", "Default no duplicates message"),
                "No duplicate or suspicious duplicate images found."
            ))

    def show_duplicates(self, duplicate_groups, suspicious_groups, all_image_hashes):
        for idx, group in enumerate(duplicate_groups, 1):
            self.create_group_frame(group, idx, self._get_lang_text("GROUP_TYPE_DUPLICATE", "Default duplicate group type"), all_image_hashes)
        for idx, group in enumerate(suspicious_groups, 1):
            self.create_group_frame(group, idx, self._get_lang_text("GROUP_TYPE_SUSPICIOUS", "Default suspicious group type"), all_image_hashes)

    def create_group_frame(self, group, idx, group_type, all_image_hashes):
        group_frame = ttk.LabelFrame(
            self.result_frame,
            text=self._get_lang_text("GROUP_LABEL", "Default group label").format(group_type, idx),
            padding=10
        )
        group_frame.pack(fill=tk.X, padx=5, pady=5)
        check_vars = {}
        for col, img_path in enumerate(group):
            img_frame = ttk.Frame(group_frame)
            img_frame.grid(row=0, column=col, padx=10, pady=5)
            file_name = os.path.basename(img_path)
            file_size = os.path.getsize(img_path)
            size_str = self._format_file_size(file_size)
            file_date = time.ctime(os.path.getmtime(img_path))

            ttk.Label(img_frame, text=self._get_lang_text("FILE_NAME", "Default file name label").format(file_name)).pack()
            ttk.Label(img_frame, text=self._get_lang_text("FILE_SIZE", "Default file size label").format(size_str)).pack()

            try:
                with Image.open(img_path) as img:
                    width, height = img.size
                    dimensions_str = self._get_lang_text("DIMENSIONS", "Default dimensions format").format(width, height)
                    ttk.Label(img_frame, text=dimensions_str).pack()
            except Exception as e:
                ttk.Label(img_frame, text=self._get_lang_text("INFO_WIDTH_ERROR", "Default width and height info error message")).pack()

            ttk.Label(img_frame, text=self._get_lang_text("MODIFIED_TIME", "Default modified time label").format(file_date)).pack()

            try:
                thumbnail = self.get_cached_image(img_path, (150, 150))
                label = ttk.Label(img_frame, image=thumbnail)
                label.bind('<Button-1>', lambda e, path=img_path: self.show_large_image(path))
                label.image = thumbnail
                label.pack()
            except Exception as e:
                ttk.Label(img_frame, text=self._get_lang_text("LOADING_ERROR", "Default image loading error message")).pack()

            hash_text = "\n".join(
                f"{hash_type}: {all_image_hashes[img_path][hash_type]}" for hash_type in all_image_hashes[img_path]
            )
            ttk.Label(img_frame, text=hash_text).pack()

            check_vars[img_path] = tk.IntVar(value=0)
            cb = ttk.Checkbutton(
                img_frame,
                text=self._get_lang_text("BTN_DELETE_IMAGE", "Delete it🗑️"),
                variable=check_vars[img_path]
            )
            cb.pack()

        button_sub_frame = ttk.Frame(group_frame)
        button_sub_frame.grid(row=1, column=0, columnspan=len(group), pady=5, sticky=tk.W)

        select_all_sub_btn = ttk.Button(
            button_sub_frame,
            text=self._get_lang_text("BTN_SELECT_ALL", "Default select all button text"),
            command=lambda vs=check_vars: self.select_all_in_group(vs)
        )
        select_all_sub_btn.pack(side=tk.LEFT, padx=5)

        invert_selection_sub_btn = ttk.Button(
            button_sub_frame,
            text=self._get_lang_text("BTN_INVERT", "Default invert selection button text"),
            command=lambda vs=check_vars: self.invert_selection_in_group(vs)
        )
        invert_selection_sub_btn.pack(side=tk.LEFT, padx=5)

        cancel_selection_sub_btn = ttk.Button(
            button_sub_frame,
            text=self._get_lang_text("BTN_CANCEL", "Default cancel selection button text"),
            command=lambda vs=check_vars: self.cancel_selection_in_group(vs)
        )
        cancel_selection_sub_btn.pack(side=tk.LEFT, padx=5)

        delete_selected_btn = ttk.Button(
            button_sub_frame,
            text=self._get_lang_text("BTN_DELETE", "Default delete selected button text"),
            command=lambda vs=check_vars: self.delete_selected(vs)
        )
        delete_selected_btn.pack(side=tk.LEFT, padx=5)

    def delete_selected(self, check_vars):
        deleted_files = []
        failed_files = []
        for path, var in check_vars.items():
            if var.get() == 1:
                try:
                    os.remove(path)
                    deleted_files.append(path)
                    self.log(self._get_lang_text("LOG_DELETE_SUCCESS", "Default delete success message").format(path))
                except Exception as e:
                    failed_files.append(path)
                    self.log(self._get_lang_text("LOG_DELETE_FAILED", "Default delete failed message").format(path, str(e)))
        if deleted_files:
            deleted_msg = ", ".join(deleted_files)
            self.log(f"👏Successfully deleted these images: {deleted_msg}")
        if failed_files:
            failed_msg = ", ".join(failed_files)
            self.log(f"😔Failed to delete these images: {failed_msg}")
        messagebox.showinfo(self._get_lang_text("MSG_DELETE_COMPLETE", "Default delete operation completed message"), "Operation completed!")

    def _toggle_buttons(self, state):
        state = tk.NORMAL if state else tk.DISABLED
        self.select_btn.config(state=state)
        self.check_btn.config(state=state)

    def show_progress(self):
        self.progress_bar["value"] = 0
        self.progress_bar.pack(fill=tk.X, expand=True, padx=5)

    def _update_progress(self, value):
        self.root.after(0, lambda: self.progress_bar.config(value=value))

    def hide_progress(self):
        self.progress_bar.pack_forget()

    def clear_result_frame(self):
        for widget in self.result_frame.winfo_children():
            widget.destroy()

    def _on_mousewheel(self, event):
        if self.canvas.winfo_containing(event.x_root, event.y_root):
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def log(self, message):
        current_time = time.strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{current_time}] {message}\n"
        self.log_text.insert(tk.END, log_entry)
        self.log_text.see(tk.END)

    def show_large_image(self, path):
        try:
            large_image_window = Toplevel(self.root)
            large_image_window.title(self._get_lang_text("PREVIEW_TITLE", "Default preview title").format(os.path.basename(path)))
            with Image.open(path) as img:
                screen_width = large_image_window.winfo_screenwidth()
                screen_height = large_image_window.winfo_screenheight()
                max_width = screen_width - 20
                max_height = screen_height - 20
                width, height = img.size
                if width > max_width or height > max_height:
                    ratio = min(max_width / width, max_height / height)
                    new_width = int(width * ratio)
                    new_height = int(height * ratio)
                    img = img.resize((new_width, new_height), Image.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                label = ttk.Label(large_image_window, image=photo)
                label.image = photo
                label.pack()
        except Exception as e:
            messagebox.showerror(self._get_lang_text("MSG_PREVIEW_ERROR", "Default preview error message"),
                                 f"Failed to preview the image: {str(e)}")
            self.log(self._get_lang_text("LOG_PREVIEW_FAILED", "Default preview failed message").format(path, str(e)))

    def switch_language(self):
        global CURRENT_LANGUAGE
        if CURRENT_LANGUAGE == "zh_CN":
            CURRENT_LANGUAGE = "en_US"
            self.lang_btn.config(text="切换到中文")
        else:
            CURRENT_LANGUAGE = "zh_CN"
            self.lang_btn.config(text="Switch to English")
        self._update_ui_text()

    def _update_ui_text(self):
        self.root.title(self._get_lang_text("TITLE", "Default Title"))
        self.select_btn.config(text=self._get_lang_text("SELECT_BTN_TEXT", "Default select folder button text"))
        self.check_btn.config(text=self._get_lang_text("CHECK_BTN_TEXT", "Default check hashes button text"))

    def _get_lang_text(self, key, default):
        lang_dict = load_language(CURRENT_LANGUAGE)
        return lang_dict.get(key, default)

    def _format_file_size(self, size):
        if size < 1024:
            return self._get_lang_text("FILE_SIZE_BYTES", "Default file size in bytes format").format(size)
        elif size < 1024 * 1024:
            return self._get_lang_text("FILE_SIZE_KB", "Default file size in KB format").format(size / 1024)
        else:
            return self._get_lang_text("FILE_SIZE_MB", "Default file size in MB format").format(size / (1024 * 1024))

    def _update_check_button_state(self):
        if os.path.exists("image_hashes.txt"):
            self.check_btn.config(state=tk.NORMAL)
            self.log(self._get_lang_text("LOG_HASH_FOUND", "Default hash file found message"))
        else:
            self.log(self._get_lang_text("LOG_HASH_NOT_FOUND", "Default hash file not found message"))

    def get_cached_image(self, path, size):
        if path in self.image_cache:
            self.image_cache.move_to_end(path)
            return self.image_cache[path]
        with Image.open(path) as img:
            img.thumbnail(size)
            photo = ImageTk.PhotoImage(img)
        if len(self.image_cache) >= self.MAX_CACHE_SIZE:
            self.image_cache.popitem(last=False)
        self.image_cache[path] = photo
        return photo

    def select_all_in_group(self, check_vars):
        for var in check_vars.values():
            var.set(1)

    def invert_selection_in_group(self, check_vars):
        for var in check_vars.values():
            var.set(1 - var.get())

    def cancel_selection_in_group(self, check_vars):
        for var in check_vars.values():
            var.set(0)