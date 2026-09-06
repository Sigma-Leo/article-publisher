import json
import time
import random
import io
import requests
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
import threading
import copy
from urllib.parse import urlsplit

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    Image = None
    ImageTk = None
    PIL_AVAILABLE = False


class ArticlePublisherGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("稿件批量发布工具【增强版：Cookie切换｜暂停｜选中发布】")
        self.root.geometry("1150x750")
        self.root.minsize(980, 650)
        self.setup_styles()

        self.config_path = "config.json"
        self.cookie_store_path = "cookies_store.json"
        self.article_path = "articles.json"

        self.config_data = None
        self.article_list = []
        self.cookie_list = []
        self.image_library = []
        self.image_preview_cache = {}
        self.running_publish = False  # 发布运行标记，用于暂停
        self.publish_stop_event = threading.Event()

        # ==========顶部区域==========
        top_frame = ttk.Frame(root, style="Toolbar.TFrame", padding=(12, 10))
        top_frame.pack(fill=tk.X, padx=12, pady=(12, 6))
        top_row1 = ttk.Frame(top_frame, style="Toolbar.TFrame")
        top_row1.pack(fill=tk.X, pady=(0, 5))
        top_row2 = ttk.Frame(top_frame, style="Toolbar.TFrame")
        top_row2.pack(fill=tk.X)

        ttk.Button(top_row1, text="加载 config.json", command=self.load_config).pack(side=tk.LEFT, padx=3)
        ttk.Button(top_row1, text="加载 articles.json", command=self.load_articles).pack(side=tk.LEFT, padx=3)
        ttk.Button(top_row1, text="刷新数据", command=self.hot_reload).pack(side=tk.LEFT, padx=3)
        ttk.Button(top_row1, text="保存全部稿件", style="Accent.TButton", command=self.save_all_articles).pack(side=tk.LEFT, padx=3)

        # Cookie切换区
        ttk.Label(top_row1, text="Cookie 账号", style="ToolbarLabel.TLabel").pack(side=tk.LEFT, padx=(14, 5))
        self.cookie_var = tk.StringVar()
        self.cookie_combo = ttk.Combobox(top_row1, textvariable=self.cookie_var, width=22, state="readonly")
        self.cookie_combo.pack(side=tk.LEFT, padx=2)
        ttk.Button(top_row1, text="+ 新增 Cookie", command=self.add_cookie_dialog).pack(side=tk.LEFT, padx=2)
        ttk.Button(top_row1, text="编辑", command=self.edit_cookie_dialog).pack(side=tk.LEFT, padx=2)
        ttk.Button(top_row1, text="删除", command=self.del_cookie).pack(side=tk.LEFT, padx=2)

        ttk.Separator(top_row1, orient=tk.VERTICAL).pack(side=tk.LEFT, padx=8, fill=tk.Y)

        # 发布控制
        self.btn_start = ttk.Button(top_row2, text="发布选中稿件", style="Publish.TButton", command=self.start_selected_publish)
        self.btn_start.pack(side=tk.LEFT, padx=3)
        self.btn_pause = ttk.Button(top_row2, text="暂停发布", style="Danger.TButton", command=self.stop_publish, state=tk.DISABLED)
        self.btn_pause.pack(side=tk.LEFT, padx=3)
        ttk.Label(top_row2, text="随机间隔", style="ToolbarLabel.TLabel").pack(side=tk.LEFT, padx=(12, 4))
        self.min_interval_var = tk.StringVar(value="10")
        ttk.Spinbox(top_row2, from_=0, to=3600, increment=1, textvariable=self.min_interval_var, width=5).pack(side=tk.LEFT, padx=1)
        ttk.Label(top_row2, text="至", style="ToolbarLabel.TLabel").pack(side=tk.LEFT, padx=2)
        self.max_interval_var = tk.StringVar(value="15")
        ttk.Spinbox(top_row2, from_=0, to=3600, increment=1, textvariable=self.max_interval_var, width=5).pack(side=tk.LEFT, padx=1)
        ttk.Label(top_row2, text="秒", style="ToolbarLabel.TLabel").pack(side=tk.LEFT, padx=(2, 3))

        ttk.Separator(top_row2, orient=tk.VERTICAL).pack(side=tk.LEFT, padx=8, fill=tk.Y)
        ttk.Button(top_row2, text="新建稿件", command=self.new_article).pack(side=tk.LEFT, padx=3)
        ttk.Button(top_row2, text="复制当前稿件", command=self.copy_current_article).pack(side=tk.LEFT, padx=3)
        ttk.Button(top_row2, text="删除选中稿件", style="Danger.TButton", command=self.delete_article).pack(side=tk.LEFT, padx=3)
        ttk.Button(top_row2, text="↑上移", command=self.move_up).pack(side=tk.LEFT, padx=2)
        ttk.Button(top_row2, text="↓下移", command=self.move_down).pack(side=tk.LEFT, padx=2)

        # ==========主分割面板==========
        main_pane = ttk.PanedWindow(root, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True, padx=12, pady=6)

        # 左侧稿件列表（带复选框）
        left_frame = ttk.Frame(main_pane, style="Panel.TFrame", padding=12)
        main_pane.add(left_frame, weight=1)
        ttk.Label(left_frame, text="稿件列表", style="Section.TLabel").pack(anchor="w")
        ttk.Label(left_frame, text="勾选左侧项目后批量发布", style="Hint.TLabel").pack(anchor="w", pady=(2, 8))
        self.select_all_btn = ttk.Button(left_frame, text="全选稿件", command=self.toggle_select_all)
        self.select_all_btn.pack(anchor="e", pady=(0, 6))

        self.article_tree = ttk.Treeview(left_frame, columns=("check", "title", "status"), show="headings")
        self.article_tree.heading("check", text="勾选")
        self.article_tree.heading("title", text="稿件标题")
        self.article_tree.heading("status", text="状态")
        self.article_tree.column("check", width=45, anchor=tk.CENTER)
        self.article_tree.column("title", width=240)
        self.article_tree.column("status", width=80, anchor=tk.CENTER)
        self.article_tree.pack(fill=tk.BOTH, expand=True)
        self.article_tree.bind("<<TreeviewSelect>>", self.on_select_article)
        self.article_tree.bind("<Button-1>", self.tree_click_checkbox)

        # 右侧编辑面板
        right_frame = ttk.Frame(main_pane, style="Panel.TFrame", padding=12)
        main_pane.add(right_frame, weight=2)

        ttk.Label(right_frame, text="稿件编辑", style="Section.TLabel").pack(anchor="w")
        ttk.Label(right_frame, text="标题", style="Field.TLabel").pack(anchor="w", pady=(12, 3))
        self.var_title = tk.StringVar()
        self.title_entry = ttk.Entry(right_frame, textvariable=self.var_title)
        self.title_entry.pack(fill=tk.X)
        self.bind_undo_shortcuts(self.title_entry)

        ttk.Label(right_frame, text="正文 content（直接回车换行，不要写 <br/>）", style="Field.TLabel").pack(anchor="w", pady=(10, 3))
        self.text_content = scrolledtext.ScrolledText(right_frame, height=11)
        self.text_content.configure(undo=True, maxundo=-1, bg="#FFFFFF", fg="#1D2733", insertbackground="#007AFF", relief=tk.FLAT, borderwidth=8, highlightthickness=1, highlightbackground="#D8E3EF", highlightcolor="#8FC4FF", font=("Microsoft YaHei UI", 10), padx=6, pady=6)
        self.text_content.pack(fill=tk.BOTH, expand=True)
        self.bind_undo_shortcuts(self.text_content)
        self.text_content.bind("<Control-v>", self.paste_content_with_breaks)

        cover_toolbar = ttk.Frame(right_frame, style="Panel.TFrame")
        cover_toolbar.pack(fill=tk.X, pady=(10, 3))
        ttk.Label(cover_toolbar, text="封面 pgcFeedCovers（JSON 数组）", style="Field.TLabel").pack(side=tk.LEFT)
        ttk.Button(cover_toolbar, text="预览配图", command=self.preview_current_covers).pack(side=tk.RIGHT, padx=(6, 0))
        ttk.Button(cover_toolbar, text="图片库", command=self.open_image_library).pack(side=tk.RIGHT)
        self.text_cover = scrolledtext.ScrolledText(right_frame, height=6)
        self.text_cover.configure(undo=True, maxundo=-1, bg="#FFFFFF", fg="#405364", insertbackground="#007AFF", relief=tk.FLAT, borderwidth=8, highlightthickness=1, highlightbackground="#D8E3EF", highlightcolor="#8FC4FF", font=("Consolas", 10), padx=6, pady=6)
        self.text_cover.pack(fill=tk.X)
        self.bind_undo_shortcuts(self.text_cover)

        ttk.Button(right_frame, text="保存当前稿件修改", style="Accent.TButton", command=self.save_current_article).pack(anchor="w", pady=(10, 2))

        # 日志区域
        log_frame = ttk.Frame(root, style="Log.TFrame", padding=(12, 8, 12, 12))
        log_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))
        ttk.Label(log_frame, text="运行日志", style="LogSection.TLabel").pack(anchor="w", pady=(0, 6))
        self.log_text = scrolledtext.ScrolledText(log_frame, height=10)
        self.log_text.configure(bg="#F8FBFF", fg="#526477", insertbackground="#007AFF", relief=tk.FLAT, borderwidth=8, highlightthickness=1, highlightbackground="#D8E3EF", highlightcolor="#8FC4FF", font=("Consolas", 9), padx=6, pady=6)
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # 所有UI控件创建完成之后，再自动加载本地数据
        self.load_cookie_store()
        self.load_config()
        self.load_articles()
        self.root.bind_all("<Control-s>", self.save_current_shortcut)
        self.root.bind_all("<F5>", self.hot_reload_shortcut)

    def setup_styles(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(".", font=("Microsoft YaHei UI", 10), foreground="#243447")
        style.configure("Toolbar.TFrame", background="#F8FBFF")
        style.configure("Panel.TFrame", background="#FFFFFF")
        style.configure("Log.TFrame", background="#EAF1F8")
        style.configure("ToolbarLabel.TLabel", background="#F8FBFF", foreground="#66788A")
        style.configure("Section.TLabel", background="#FFFFFF", foreground="#172B4D", font=("Microsoft YaHei UI", 13, "bold"))
        style.configure("LogSection.TLabel", background="#EAF1F8", foreground="#172B4D", font=("Microsoft YaHei UI", 12, "bold"))
        style.configure("Hint.TLabel", background="#FFFFFF", foreground="#8191A2", font=("Microsoft YaHei UI", 9))
        style.configure("Field.TLabel", background="#FFFFFF", foreground="#526477", font=("Microsoft YaHei UI", 10, "bold"))
        style.configure("TButton", padding=(10, 6), background="#FFFFFF", foreground="#405364", bordercolor="#D8E3EF", lightcolor="#FFFFFF", darkcolor="#D8E3EF")
        style.map("TButton", background=[("active", "#F0F6FC"), ("pressed", "#E3EEF9")], foreground=[("disabled", "#AAB5C0")])
        style.configure("Accent.TButton", foreground="#FFFFFF", background="#007AFF", bordercolor="#007AFF")
        style.map("Accent.TButton", background=[("active", "#006FE6"), ("pressed", "#005FC7")])
        style.configure("Publish.TButton", foreground="#FFFFFF", background="#34C759", bordercolor="#34C759", padding=(12, 6))
        style.map("Publish.TButton", background=[("active", "#2BAE4D"), ("pressed", "#249440")])
        style.configure("Danger.TButton", foreground="#D93045", bordercolor="#F1C4CB")
        style.map("Danger.TButton", foreground=[("disabled", "#AAB5BD"), ("active", "#B42336")], background=[("active", "#FFF1F3")])
        style.configure("TEntry", padding=6, fieldbackground="#FFFFFF", bordercolor="#D8E3EF", lightcolor="#FFFFFF", darkcolor="#D8E3EF")
        style.configure("TCombobox", padding=5, fieldbackground="#FFFFFF", bordercolor="#D8E3EF")
        style.configure("TSpinbox", padding=4, fieldbackground="#FFFFFF", bordercolor="#D8E3EF")
        style.configure("Treeview", background="#FFFFFF", fieldbackground="#FFFFFF", foreground="#243447", rowheight=32, borderwidth=0)
        style.configure("Treeview.Heading", background="#F1F6FB", foreground="#526477", font=("Microsoft YaHei UI", 10, "bold"), padding=8)
        style.map("Treeview", background=[("selected", "#DCEBFF")], foreground=[("selected", "#172B4D")])
        style.configure("TPanedwindow", background="#EAF1F8")
        style.configure("TSeparator", background="#D8E3EF")
        self.root.configure(background="#EAF1F8")

    def bind_undo_shortcuts(self, widget):
        widget.bind("<Control-z>", self.undo_edit)
        widget.bind("<Control-y>", self.redo_edit)

    def undo_edit(self, event):
        try:
            event.widget.edit_undo()
        except tk.TclError:
            pass
        return "break"

    def redo_edit(self, event):
        try:
            event.widget.edit_redo()
        except tk.TclError:
            pass
        return "break"

    def paste_content_with_breaks(self, event):
        try:
            pasted_text = event.widget.clipboard_get()
        except tk.TclError:
            return "break"
        if "<br/>" not in pasted_text:
            pasted_text = pasted_text.replace("\r\n", "\n").replace("\r", "\n")
            pasted_text = pasted_text.replace("\n", "<br/>\n")
        event.widget.edit_separator()
        event.widget.insert(tk.INSERT, pasted_text)
        return "break"

    def save_current_shortcut(self, event):
        self.save_current_article()
        return "break"

    def hot_reload_shortcut(self, event):
        self.hot_reload()
        return "break"

    def hot_reload(self):
        if self.running_publish:
            messagebox.showwarning("提示", "发布任务进行中，请暂停后再刷新数据")
            return
        self.load_cookie_store()
        self.load_config()
        self.image_library.clear()
        self.image_preview_cache.clear()
        self.load_articles()
        self.log("🔄数据已热更新，无需重启程序")

    def log(self, msg):
        if threading.current_thread() is not threading.main_thread():
            self.root.after(0, self.log, msg)
            return
        self.log_text.insert(tk.END, f"{time.strftime('%H:%M:%S')} {msg}\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()

    # ================= Cookie存储切换模块 =================
    def load_cookie_store(self):
        try:
            with open(self.cookie_store_path, "r", encoding="utf-8") as f:
                self.cookie_list = json.load(f)
        except Exception:
            self.cookie_list = []
        self.refresh_cookie_combo()

    def save_cookie_store(self):
        with open(self.cookie_store_path, "w", encoding="utf-8") as f:
            json.dump(self.cookie_list, f, ensure_ascii=False, indent=2)
        self.refresh_cookie_combo()

    def refresh_cookie_combo(self):
        names = [item["name"] for item in self.cookie_list]
        self.cookie_combo["values"] = names
        if len(names) > 0:
            self.cookie_combo.current(0)

    def add_cookie_dialog(self):
        win = tk.Toplevel(self.root)
        win.title("新增Cookie账号")
        win.geometry("620x320")
        ttk.Label(win, text="账号别名：").pack(anchor="w")
        var_name = tk.StringVar()
        ttk.Entry(win, textvariable=var_name).pack(fill=tk.X, padx=6)
        ttk.Label(win, text="Cookie完整字符串：").pack(anchor="w")
        txt = scrolledtext.ScrolledText(win, height=12)
        txt.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)

        def ok():
            n = var_name.get().strip()
            c = txt.get(1.0, tk.END).strip()
            if not n or not c:
                messagebox.showwarning("提示", "别名和Cookie不能为空")
                return
            self.cookie_list.append({"name": n, "cookie": c})
            self.save_cookie_store()
            self.log(f"✅新增Cookie账号 [{n}]")
            win.destroy()
        ttk.Button(win, text="确认保存", command=ok).pack(pady=4)

    def edit_cookie_dialog(self):
        idx = self.cookie_combo.current()
        if idx < 0:
            messagebox.showwarning("提示", "请先选择一个Cookie")
            return
        item = self.cookie_list[idx]
        win = tk.Toplevel(self.root)
        win.title("编辑Cookie")
        win.geometry("620x320")
        ttk.Label(win, text="账号别名").pack(anchor="w")
        var_name = tk.StringVar(value=item["name"])
        ttk.Entry(win, textvariable=var_name).pack(fill=tk.X, padx=6)
        ttk.Label(win, text="Cookie字符串").pack(anchor="w")
        txt = scrolledtext.ScrolledText(win, height=12)
        txt.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)
        txt.insert(tk.END, item["cookie"])

        def ok():
            n = var_name.get().strip()
            c = txt.get(1.0, tk.END).strip()
            if not n or not c:
                return
            self.cookie_list[idx]["name"] = n
            self.cookie_list[idx]["cookie"] = c
            self.save_cookie_store()
            self.log(f"✅更新Cookie [{n}]")
            win.destroy()
        ttk.Button(win, text="保存", command=ok).pack(pady=4)

    def del_cookie(self):
        idx = self.cookie_combo.current()
        if idx <0:
            return
        name = self.cookie_list[idx]["name"]
        if messagebox.askyesno("确认删除", f"确定删除账号【{name}】？"):
            del self.cookie_list[idx]
            self.save_cookie_store()
            self.log(f"🗑删除Cookie账号 [{name}]")

    def get_current_cookie(self):
        idx = self.cookie_combo.current()
        if idx <0 or len(self.cookie_list)==0:
            return None
        return self.cookie_list[idx]["cookie"]

    # ================= 稿件CRUD + 排序 =================
    def load_config(self):
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                self.config_data = json.load(f)
            self.config_data.pop("cookie", None)
            self.log(f"✅加载config成功 base_url={self.config_data['base_url']}")
        except Exception as e:
            messagebox.showerror("错误", f"读取config失败:{e}")

    def load_articles(self):
        try:
            with open(self.article_path, "r", encoding="utf-8") as f:
                self.article_list = json.load(f)
            for item in self.article_tree.get_children():
                self.article_tree.delete(item)
            for idx, art in enumerate(self.article_list):
                self.article_tree.insert("", tk.END, iid=str(idx), values=("☐", art["title"], "待发布"))
            self.update_select_all_button()
            self.log(f"✅加载稿件，共{len(self.article_list)}篇")
        except Exception as e:
            messagebox.showerror("错误", f"读取articles失败:{e}")

    @staticmethod
    def image_identity(image):
        resource_id = str(image.get("id", "")).strip()
        if resource_id:
            return f"id:{resource_id}"
        url = image.get("url") or image.get("preview_url") or ""
        parsed = urlsplit(url)
        return f"url:{parsed.scheme.lower()}://{parsed.netloc.lower()}{parsed.path}"

    @classmethod
    def deduplicate_images(cls, images):
        unique = {}
        for image in images:
            key = cls.image_identity(image)
            if key and key not in unique:
                unique[key] = image
        return list(unique.values())

    def open_image_library(self):
        win = tk.Toplevel(self.root)
        win.title("图片库")
        win.geometry("1000x680")
        win.minsize(760, 480)
        win.transient(self.root)
        ttk.Label(win, text="选择配图（勾选多张，点击图片查看大图）", style="Section.TLabel").pack(anchor="w", padx=14, pady=(14, 6))
        canvas_frame = ttk.Frame(win, padding=(14, 0, 14, 8))
        canvas_frame.pack(fill=tk.BOTH, expand=True)
        canvas = tk.Canvas(canvas_frame, bg="#F4F8FC", highlightthickness=0)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=canvas.yview).pack(side=tk.RIGHT, fill=tk.Y)
        grid_frame = ttk.Frame(canvas, style="Panel.TFrame", padding=10)
        canvas_window = canvas.create_window((0, 0), window=grid_frame, anchor="nw")
        preview_cache = self.image_preview_cache
        selected_vars = {}
        failed_urls = set()
        page_var = tk.IntVar(value=1)

        canvas.configure(yscrollcommand=lambda first, last: scrollbar.set(first, last))
        scrollbar = canvas_frame.winfo_children()[-1]
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(canvas_window, width=max(event.width, 500)))
        grid_frame.bind("<Configure>", lambda event: canvas.configure(scrollregion=canvas.bbox("all")))

        def show_preview(image):
            preview = tk.Toplevel(win)
            preview.title("图片预览")
            preview.geometry("720x560")
            label = ttk.Label(preview, text="加载预览中...", anchor=tk.CENTER)
            label.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)
            url = image.get("preview_url") or image.get("url", "")
            if url in preview_cache:
                label.configure(image=preview_cache[url], text="")
                label.image = preview_cache[url]
            else:
                threading.Thread(target=self.load_image_preview, args=(url, label, preview_cache, (620, 460)), daemon=True).start()

        def refresh_grid():
            for child in grid_frame.winfo_children():
                child.destroy()
            selected_vars.clear()
            for index, image in enumerate(self.image_library):
                url = image.get("preview_url") or image.get("url", "")
                if url in failed_urls:
                    continue
                card = ttk.Frame(grid_frame, style="Panel.TFrame", padding=6, relief=tk.GROOVE)
                card.grid(row=index // 4, column=index % 4, padx=6, pady=6, sticky="nsew")
                variable = tk.BooleanVar(value=False)
                selected_vars[index] = variable
                ttk.Checkbutton(card, text="选择", variable=variable).pack(anchor="w")
                image_label = ttk.Label(card, text="加载中...", anchor=tk.CENTER, width=22)
                image_label.pack(fill=tk.BOTH, expand=True, pady=4)
                image_label.bind("<Button-1>", lambda event, item=image: show_preview(item))
                if url in preview_cache:
                    image_label.configure(image=preview_cache[url], text="")
                    image_label.image = preview_cache[url]
                else:
                    threading.Thread(target=self.load_image_preview, args=(url, image_label, preview_cache, (190, 130), lambda failed_url=url: hide_failed_image(failed_url)), daemon=True).start()
                ttk.Label(card, text=f"{image.get('width', '?')} x {image.get('height', '?')}", style="Hint.TLabel").pack(anchor="w")
            canvas.configure(scrollregion=canvas.bbox("all"))

        def hide_failed_image(url):
            failed_urls.add(url)
            refresh_grid()

        refresh_grid()
        button_frame = ttk.Frame(win, padding=(14, 0, 14, 14))
        button_frame.pack(fill=tk.X)
        ttk.Button(button_frame, text="上一页", command=lambda: self.change_image_page(page_var, -1, refresh_grid)).pack(side=tk.LEFT)
        ttk.Button(button_frame, text="从接口加载", command=lambda: self.fetch_image_library(refresh_grid, page_var.get())).pack(side=tk.LEFT, padx=8)
        ttk.Label(button_frame, textvariable=page_var).pack(side=tk.LEFT)
        ttk.Button(button_frame, text="下一页", command=lambda: self.change_image_page(page_var, 1, refresh_grid)).pack(side=tk.LEFT, padx=(8, 14))
        ttk.Button(button_frame, text="删除选中图片", style="Danger.TButton", command=lambda: self.delete_images_from_library(selected_vars, refresh_grid, win)).pack(side=tk.LEFT, padx=8)

        def use_selected_images():
            selected = [index for index, variable in selected_vars.items() if variable.get()]
            if not selected:
                messagebox.showwarning("提示", "请先选择至少一张图片", parent=win)
                return
            self.text_cover.delete(1.0, tk.END)
            self.text_cover.insert(tk.END, json.dumps([copy.deepcopy(self.image_library[index]) for index in selected], ensure_ascii=False, indent=2))
            self.log(f"🖼已选择 {len(selected)} 张配图")
            win.destroy()

        ttk.Button(button_frame, text="使用选中图片", style="Accent.TButton", command=use_selected_images).pack(side=tk.RIGHT, padx=8)
        ttk.Button(button_frame, text="关闭", command=win.destroy).pack(side=tk.RIGHT)

    def delete_images_from_library(self, selected_vars, refresh_grid, parent):
        selected = [index for index, variable in selected_vars.items() if variable.get()]
        if not selected:
            messagebox.showwarning("提示", "请先选择要删除的图片", parent=parent)
            return
        if not messagebox.askyesno("确认删除", f"确定从图片库删除选中的 {len(selected)} 张图片？", parent=parent):
            return
        selected_urls = {self.image_library[index].get("url") for index in selected}
        self.image_library = [image for image in self.image_library if image.get("url") not in selected_urls]
        refresh_grid()
        self.log(f"🗑从图片库删除 {len(selected_urls)} 张图片")

    def load_image_preview(self, url, preview_label, preview_cache, preview_size=(330, 260), on_failed=None):
        if not PIL_AVAILABLE:
            self.root.after(0, lambda: self.handle_preview_failure(preview_label, "预览需要 Pillow\n请运行：pip install Pillow", on_failed))
            return
        try:
            headers = self.config_data.get("headers", {}).copy() if self.config_data else {}
            cookie = self.get_current_cookie()
            if cookie:
                headers["Cookie"] = cookie
            headers["Referer"] = "https://www.autoengine.com/jdc/dealer/info/Article"
            headers.setdefault("User-Agent", "Mozilla/5.0")
            response = requests.get(url, headers=headers, timeout=20)
            response.raise_for_status()
            image = Image.open(io.BytesIO(response.content)).convert("RGB")
            image.thumbnail(preview_size, Image.Resampling.LANCZOS)
            image_bytes = io.BytesIO()
            image.save(image_bytes, format="PNG")
            self.root.after(0, lambda: self.update_image_preview(preview_label, url, image_bytes.getvalue(), preview_cache))
        except Exception as error:
            error_text = str(error)
            if "403" in error_text:
                error_text += "\n图片链接可能已过期，请点击“从接口加载”获取最新图片"
            self.root.after(0, lambda: self.handle_preview_failure(preview_label, f"预览失败\n{error_text}", on_failed))

    @staticmethod
    def handle_preview_failure(preview_label, message, on_failed=None):
        if on_failed:
            on_failed()
        else:
            preview_label.configure(image="", text=message)

    @staticmethod
    def update_image_preview(preview_label, url, image_bytes, preview_cache):
        photo = ImageTk.PhotoImage(data=image_bytes)
        preview_cache[url] = photo
        preview_label.configure(image=photo, text="")
        preview_label.image = photo

    def preview_current_covers(self):
        try:
            covers = json.loads(self.text_cover.get(1.0, tk.END).strip() or "[]")
            if not isinstance(covers, list):
                raise ValueError("封面内容必须是 JSON 数组")
            covers = [item for item in covers if isinstance(item, dict) and item.get("url")]
        except (ValueError, json.JSONDecodeError) as error:
            messagebox.showwarning("预览失败", f"封面 JSON 格式错误：{error}")
            return
        if not covers:
            messagebox.showinfo("预览配图", "当前稿件没有可预览的配图")
            return

        win = tk.Toplevel(self.root)
        win.title("当前稿件配图预览")
        win.geometry("860x560")
        win.minsize(620, 420)
        win.transient(self.root)
        ttk.Label(win, text=f"当前稿件配图（{len(covers)} 张）", style="Section.TLabel").pack(anchor="w", padx=14, pady=(14, 6))
        canvas_frame = ttk.Frame(win, padding=(14, 0, 14, 14))
        canvas_frame.pack(fill=tk.BOTH, expand=True)
        canvas = tk.Canvas(canvas_frame, bg="#F4F8FC", highlightthickness=0)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=canvas.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.configure(yscrollcommand=scrollbar.set)
        grid_frame = ttk.Frame(canvas, style="Panel.TFrame", padding=10)
        canvas_window = canvas.create_window((0, 0), window=grid_frame, anchor="nw")
        preview_cache = self.image_preview_cache
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(canvas_window, width=max(event.width, 500)))
        grid_frame.bind("<Configure>", lambda event: canvas.configure(scrollregion=canvas.bbox("all")))

        def show_large_preview(image):
            preview = tk.Toplevel(win)
            preview.title("配图预览")
            preview.geometry("720x560")
            label = ttk.Label(preview, text="加载预览中...", anchor=tk.CENTER)
            label.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)
            url = image.get("preview_url") or image.get("url")
            if url in preview_cache:
                label.configure(image=preview_cache[url], text="")
                label.image = preview_cache[url]
            else:
                threading.Thread(target=self.load_image_preview, args=(url, label, preview_cache, (620, 460)), daemon=True).start()

        for index, image in enumerate(covers):
            card = ttk.Frame(grid_frame, style="Panel.TFrame", padding=6, relief=tk.GROOVE)
            card.grid(row=index // 4, column=index % 4, padx=6, pady=6, sticky="nsew")
            image_label = ttk.Label(card, text="加载中...", anchor=tk.CENTER, width=22)
            image_label.pack(fill=tk.BOTH, expand=True, pady=4)
            image_label.bind("<Button-1>", lambda event, item=image: show_large_preview(item))
            url = image.get("preview_url") or image.get("url")
            if url in preview_cache:
                image_label.configure(image=preview_cache[url], text="")
                image_label.image = preview_cache[url]
            else:
                threading.Thread(target=self.load_image_preview, args=(url, image_label, preview_cache, (190, 130)), daemon=True).start()
            ttk.Label(card, text=f"{image.get('width', '?')} x {image.get('height', '?')}", style="Hint.TLabel").pack(anchor="w")

    def change_image_page(self, page_var, delta, refresh_grid):
        page = max(1, page_var.get() + delta)
        page_var.set(page)
        self.fetch_image_library(refresh_grid, page)

    def fetch_image_library(self, refresh_grid, page_index=1):
        cookie = self.get_current_cookie()
        if not cookie:
            messagebox.showwarning("提示", "请先选择 Cookie 账号")
            return
        threading.Thread(target=self.fetch_image_library_thread, args=(cookie, refresh_grid, page_index), daemon=True).start()

    def fetch_image_library_thread(self, cookie, refresh_grid, page_index):
        try:
            headers = self.config_data.get("headers", {}).copy() if self.config_data else {}
            headers["Cookie"] = cookie
            headers["Referer"] = "https://www.autoengine.com/jdc/dealer/info/Article"
            response = requests.get(
                "https://www.autoengine.com/motor/dealer_admin/article/get_media_source_new",
                params={"resource_type": 3, "is_saved": 0, "page_index": page_index, "page_size": 100},
                headers=headers,
                timeout=30,
            )
            response.raise_for_status()
            images = self.extract_image_objects(response.json())
            self.root.after(0, lambda: self.merge_remote_images(images, refresh_grid))
        except Exception as error:
            self.root.after(0, lambda: messagebox.showerror("图片库加载失败", str(error)))

    @classmethod
    def extract_image_objects(cls, payload):
        images = []
        if isinstance(payload, dict):
            url = payload.get("url") or payload.get("image_url") or payload.get("imageUrl") or payload.get("ResourceURL")
            preview_url = payload.get("preview_url") or payload.get("LiteResourceURL") or url
            if isinstance(url, str) and url.startswith("URLs://"):
                url = "https://" + url[7:]
            if isinstance(preview_url, str) and preview_url.startswith("URLs://"):
                preview_url = "https://" + preview_url[7:]
            if isinstance(url, str) and url.startswith(("http://", "https://")):
                width = payload.get("width") or payload.get("image_width") or 280
                height = payload.get("height") or payload.get("image_height") or 210
                image = copy.deepcopy(payload)
                image["url"] = url
                image["preview_url"] = preview_url
                if payload.get("ResourceID"):
                    image["id"] = payload["ResourceID"]
                image.setdefault("width", width)
                image.setdefault("height", height)
                image.setdefault("thumbWidth", width)
                image.setdefault("thumbHeight", height)
                image.setdefault("uri", "")
                image.setdefault("originUri", "")
                image.setdefault("id", "")
                images.append(image)
            for value in payload.values():
                images.extend(cls.extract_image_objects(value))
        elif isinstance(payload, list):
            for item in payload:
                images.extend(cls.extract_image_objects(item))
        unique = {}
        for image in images:
            unique[image["url"]] = image
        return list(unique.values())

    def merge_remote_images(self, images, refresh_grid):
        if not images:
            messagebox.showinfo("图片库", "接口未返回可用图片")
            return
        existing = {self.image_identity(item) for item in self.image_library}
        self.image_library.extend(image for image in images if self.image_identity(image) not in existing)
        self.image_library = self.deduplicate_images(self.image_library)
        refresh_grid()
        self.log(f"🖼从接口加载 {len(images)} 张图片")

    def tree_click_checkbox(self, event):
        item = self.article_tree.identify_row(event.y)
        if not item:
            return "break"
        self.article_tree.selection_set(item)
        col = self.article_tree.identify_column(event.x)
        if col == "#1":
            val = self.article_tree.item(item, "values")
            if val[0] == "☐":
                self.article_tree.item(item, values=("☑", val[1], val[2]))
            else:
                self.article_tree.item(item, values=("☐", val[1], val[2]))
            self.update_select_all_button()
            return "break"

    def toggle_select_all(self):
        items = self.article_tree.get_children()
        if not items:
            return
        should_select = any(self.article_tree.item(item, "values")[0] == "☐" for item in items)
        for item in items:
            values = self.article_tree.item(item, "values")
            self.article_tree.item(item, values=("☑" if should_select else "☐", values[1], values[2]))
        self.update_select_all_button()

    def update_article_status(self, index, status):
        def update():
            item = str(index)
            if self.article_tree.exists(item):
                values = self.article_tree.item(item, "values")
                self.article_tree.item(item, values=(values[0], values[1], status))
        if threading.current_thread() is threading.main_thread():
            update()
        else:
            self.root.after(0, update)

    def update_select_all_button(self):
        if not hasattr(self, "select_all_btn"):
            return
        items = self.article_tree.get_children()
        all_selected = bool(items) and all(self.article_tree.item(item, "values")[0] == "☑" for item in items)
        self.select_all_btn.configure(text="取消全选" if all_selected else "全选稿件")

    def get_checked_indexes(self):
        checked = []
        for iid in self.article_tree.get_children():
            vals = self.article_tree.item(iid, "values")
            if vals[0] == "☑":
                checked.append(int(iid))
        return checked

    def on_select_article(self, event):
        sel = self.article_tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        art = self.article_list[idx]
        self.var_title.set(art["title"])
        self.text_content.delete(1.0, tk.END)
        self.text_content.insert(tk.END, art["content"])
        self.text_cover.delete(1.0, tk.END)
        self.text_cover.insert(tk.END, json.dumps(art["extra"]["pgcFeedCovers"], ensure_ascii=False, indent=2))

    def save_current_article(self):
        sel = self.article_tree.selection()
        if not sel:
            return
        try:
            idx = int(sel[0])
            art = self.article_list[idx]
            art["title"] = self.var_title.get()
            art["content"] = self.text_content.get(1.0, tk.END).rstrip("\n")
            cover_text = self.text_cover.get(1.0, tk.END).strip()
            art["extra"]["pgcFeedCovers"] = json.loads(cover_text)
            self.write_articles_file()
            self.log("💾当前稿件已保存到 articles.json")
        except (ValueError, json.JSONDecodeError) as error:
            messagebox.showwarning("保存失败", f"封面 JSON 格式错误：{error}")

    def write_articles_file(self):
        with open(self.article_path, "w", encoding="utf-8") as f:
            json.dump(self.article_list, f, ensure_ascii=False, indent=2)

    def save_all_articles(self):
        self.write_articles_file()
        self.load_articles()
        self.log("✅全部稿件已保存到articles.json")

    def new_article(self):
        new_item = {
            "title":"新建稿件",
            "content":"",
            "extra":{"pgcFeedCovers":[]},
            "aid":0
        }
        self.article_list.append(new_item)
        self.save_all_articles()

    def copy_current_article(self):
        sel = self.article_tree.selection()
        if not sel:
            messagebox.showinfo("提示","请选中一篇稿件")
            return
        idx=int(sel[0])
        dup = copy.deepcopy(self.article_list[idx])
        dup["title"] = dup["title"] + "【副本】"
        self.article_list.append(dup)
        self.save_all_articles()

    def delete_article(self):
        sel = self.article_tree.selection()
        if not sel:
            return
        idx=int(sel[0])
        title = self.article_list[idx]["title"]
        if messagebox.askyesno("确认删除", f"确定删除稿件：{title}"):
            del self.article_list[idx]
            self.save_all_articles()

    def move_up(self):
        sel = self.article_tree.selection()
        if not sel:
            return
        idx=int(sel[0])
        if idx <= 0:
            return
        self.article_list[idx], self.article_list[idx-1] = self.article_list[idx-1], self.article_list[idx]
        self.save_all_articles()
        self.article_tree.selection_set(str(idx-1))

    def move_down(self):
        sel = self.article_tree.selection()
        if not sel:
            return
        idx=int(sel[0])
        if idx >= len(self.article_list)-1:
            return
        self.article_list[idx], self.article_list[idx+1] = self.article_list[idx+1], self.article_list[idx]
        self.save_all_articles()
        self.article_tree.selection_set(str(idx+1))

    # =====================发布逻辑（后台线程，支持暂停）=====================
    def publish_one(self, article):
        headers = self.config_data["headers"].copy()
        cookie = self.get_current_cookie()
        if not cookie:
            return {"error":"未选择Cookie"}
        headers["Cookie"] = cookie
        last_error = None
        for attempt in range(1, 4):
            try:
                resp = requests.post(
                    url=self.config_data["base_url"],
                    headers=headers,
                    json=article,
                    timeout=30
                )
                response_data = None
                try:
                    response_data = resp.json()
                except ValueError:
                    pass
                business_status = response_data.get("status") if isinstance(response_data, dict) else None
                business_failed = isinstance(business_status, (int, float)) and business_status >= 400
                prompt = response_data.get("prompts", "") if isinstance(response_data, dict) else ""
                if isinstance(prompt, str) and any(word in prompt for word in ("失败", "错误", "异常")):
                    business_failed = True
                success = 200 <= resp.status_code < 300 and not business_failed
                result = {
                    "success": success,
                    "status_code": resp.status_code,
                    "business_status": business_status,
                    "text": resp.text,
                    "attempt": attempt,
                }
                retryable = resp.status_code >= 500 or business_failed
                if not retryable or attempt == 3:
                    return result
                self.log(f"接口返回失败（HTTP {resp.status_code}，业务状态 {business_status}），第 {attempt}/3 次重试")
            except requests.RequestException as error:
                last_error = str(error)
                if attempt < 3:
                    self.log(f"网络错误，第 {attempt}/3 次重试：{last_error}")
        return {"error": last_error or "请求失败", "attempt": 3}

    def publish_thread(self, index_list, min_interval, max_interval):
        total = len(index_list)
        self.log(f"====开始发布选中{total}篇稿件====")
        self.running_publish = True
        self.publish_stop_event.clear()
        self.root.after(0, lambda: self.btn_start.config(state=tk.DISABLED))
        self.root.after(0, lambda: self.btn_pause.config(state=tk.NORMAL))

        for pos,art_idx in enumerate(index_list):
            if not self.running_publish or self.publish_stop_event.is_set():
                self.log("🛑用户手动暂停发布任务")
                break
            art = self.article_list[art_idx]
            self.update_article_status(art_idx, "发布中")
            self.log(f"\n【{pos+1}/{total}】{art['title']}")
            res = self.publish_one(art)
            self.log(str(res))
            if res.get("success", False):
                self.update_article_status(art_idx, "发布成功")
            else:
                self.update_article_status(art_idx, "发布失败")
            if pos != total-1 and self.running_publish and not self.publish_stop_event.is_set():
                interval = random.uniform(min_interval, max_interval)
                self.log(f"等待 {interval:.1f}s")
                if self.publish_stop_event.wait(interval):
                    self.log("🛑用户手动暂停发布任务")
                    break

        self.running_publish = False
        self.publish_stop_event.clear()
        self.root.after(0, lambda: self.btn_start.config(state=tk.NORMAL))
        self.root.after(0, lambda: self.btn_pause.config(state=tk.DISABLED))
        self.log("\n====发布任务结束====")

    def start_selected_publish(self):
        if not self.config_data:
            messagebox.showwarning("提示","请先加载config.json")
            return
        checked = self.get_checked_indexes()
        if len(checked) == 0:
            messagebox.showwarning("提示","请勾选至少一篇稿件！左侧列表点击☐列勾选")
            return
        if not self.get_current_cookie():
            messagebox.showwarning("提示","请先添加并选择Cookie账号")
            return
        try:
            min_interval = float(self.min_interval_var.get())
            max_interval = float(self.max_interval_var.get())
        except ValueError:
            messagebox.showwarning("提示", "随机间隔必须填写数字")
            return
        if min_interval < 0 or max_interval < 0 or min_interval > max_interval:
            messagebox.showwarning("提示", "请确认随机间隔为非负数字，且最小值不大于最大值")
            return
        t = threading.Thread(target=self.publish_thread, args=(checked, min_interval, max_interval), daemon=True)
        t.start()

    def stop_publish(self):
        self.running_publish = False
        self.publish_stop_event.set()


if __name__ == "__main__":
    win = tk.Tk()
    app = ArticlePublisherGUI(win)
    win.mainloop()
