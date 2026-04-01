#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Remember - 本地提醒/待办工具
一个简洁的桌面提醒应用程序
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import json
import os
from datetime import datetime, timedelta
from threading import Thread
import time


class Task:
    """任务数据模型"""
    def __init__(self, title, description="", due_time=None, repeat=None, completed=False, task_id=None, delay_minutes=30, sound_file=None):
        self.id = task_id or str(int(time.time() * 1000))
        self.title = title
        self.description = description
        self.due_time = due_time  # 格式: "YYYY-MM-DD HH:MM"
        self.repeat = repeat  # None, "daily", "weekly", "monthly"
        self.completed = completed
        self.delay_minutes = delay_minutes  # 延迟提醒分钟数，默认30分钟
        self.sound_file = sound_file  # 自定义铃声文件路径
        self.created_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "due_time": self.due_time,
            "repeat": self.repeat,
            "completed": self.completed,
            "delay_minutes": self.delay_minutes,
            "sound_file": self.sound_file,
            "created_at": self.created_at
        }
    
    @classmethod
    def from_dict(cls, data):
        task = cls(
            title=data["title"],
            description=data.get("description", ""),
            due_time=data.get("due_time"),
            repeat=data.get("repeat"),
            completed=data.get("completed", False),
            task_id=data.get("id"),
            delay_minutes=data.get("delay_minutes", 30),
            sound_file=data.get("sound_file")
        )
        task.created_at = data.get("created_at", task.created_at)
        return task

    def get_actual_reminder_time(self):
        """获取实际提醒时间（提前提醒）"""
        if not self.due_time:
            return None
        try:
            due = datetime.strptime(self.due_time, "%Y-%m-%d %H:%M")
            # 提前提醒（比如提前30分钟）
            actual = due - timedelta(minutes=self.delay_minutes)
            return actual
        except:
            return None


class TaskManager:
    """任务管理器 - 负责数据的增删改查"""
    def __init__(self, data_file="tasks.json"):
        self.data_file = data_file
        self.tasks = []
        self.load_tasks()
    
    def load_tasks(self):
        """从文件加载任务"""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.tasks = [Task.from_dict(t) for t in data]
            except Exception as e:
                print(f"加载任务失败: {e}")
                self.tasks = []
        else:
            self.tasks = []
    
    def save_tasks(self):
        """保存任务到文件"""
        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump([t.to_dict() for t in self.tasks], f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存任务失败: {e}")
            return False
    
    def add_task(self, task):
        """添加新任务"""
        self.tasks.append(task)
        return self.save_tasks()
    
    def delete_task(self, task_id):
        """删除任务"""
        self.tasks = [t for t in self.tasks if t.id != task_id]
        return self.save_tasks()
    
    def update_task(self, task_id, **kwargs):
        """更新任务"""
        for task in self.tasks:
            if task.id == task_id:
                for key, value in kwargs.items():
                    if hasattr(task, key):
                        setattr(task, key, value)
                return self.save_tasks()
        return False
    
    def get_pending_tasks(self):
        """获取未完成的任务"""
        return [t for t in self.tasks if not t.completed]
    
    def get_completed_tasks(self):
        """获取已完成的任务"""
        return [t for t in self.tasks if t.completed]
    
    def get_due_soon_tasks(self, minutes=30):
        """获取即将到期的任务（按实际提醒时间）"""
        now = datetime.now()
        due_soon = []
        for task in self.get_pending_tasks():
            actual_time = task.get_actual_reminder_time()
            if actual_time:
                if now <= actual_time <= now + timedelta(minutes=minutes):
                    due_soon.append(task)
        return due_soon


class ReminderThread(Thread):
    """提醒线程 - 后台检查即将到期的任务"""
    def __init__(self, task_manager, on_popup, on_sound, on_message):
        super().__init__(daemon=True)
        self.task_manager = task_manager
        self.on_popup = on_popup      # 弹窗提醒回调
        self.on_sound = on_sound      # 声音提醒回调
        self.on_message = on_message  # 消息提醒回调
        self.running = True
        self.checked_popup = set()    # 记录已弹窗提醒的任务
        self.checked_sound = set()    # 记录已声音提醒的任务
        self.checked_message = set()  # 记录已消息提醒的任务

    def run(self):
        while self.running:
            try:
                now = datetime.now()
                for task in self.task_manager.get_pending_tasks():
                    actual_time = task.get_actual_reminder_time()
                    if actual_time:
                        time_until = (actual_time - now).total_seconds() / 60  # 分钟

                        # 1. 30分钟前 - 发送消息提醒（只提醒一次，无声音）
                        if 29 <= time_until <= 30:
                            msg_key = f"msg_{task.id}_{actual_time.strftime('%Y-%m-%d %H:%M')}"
                            if msg_key not in self.checked_message:
                                self.checked_message.add(msg_key)
                                self.on_message(task, int(time_until))

                        # 2. 10分钟内 - 播放声音提醒（每2分钟提醒一次）
                        if 0 < time_until <= 10:
                            sound_key = f"sound_{task.id}_{int(time_until / 2)}"
                            if sound_key not in self.checked_sound:
                                self.checked_sound.add(sound_key)
                                self.on_sound(task, int(time_until))

                        # 3. 实际提醒时间 - 弹窗提醒（只提醒一次）
                        if actual_time - timedelta(minutes=1) <= now <= actual_time + timedelta(minutes=1):
                            popup_key = f"popup_{task.id}_{actual_time.strftime('%Y-%m-%d %H:%M')}"
                            if popup_key not in self.checked_popup:
                                self.checked_popup.add(popup_key)
                                self.on_popup(task)

                # 每天清理一次已检查记录
                if now.hour == 0 and now.minute == 0:
                    self.checked_popup.clear()
                    self.checked_sound.clear()
                    self.checked_message.clear()

                time.sleep(10)  # 每10秒检查一次，更精确
            except Exception as e:
                print(f"提醒线程错误: {e}")
                time.sleep(20)

    def stop(self):
        self.running = False


class AddTaskDialog(tk.Toplevel):
    """添加/编辑任务对话框"""
    def __init__(self, parent, task=None):
        super().__init__(parent)
        self.task = task
        self.result = None
        
        self.title("编辑任务" if task else "添加任务")
        self.geometry("400x350")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        
        self.create_widgets()
        
        if task:
            self.fill_data()
        
        self.center_window()
    
    def center_window(self):
        """居中窗口"""
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')
    
    def create_widgets(self):
        padding = {"padx": 15, "pady": 10}
        
        # 标题
        tk.Label(self, text="任务标题:", font=("Microsoft YaHei", 10)).pack(anchor="w", **padding)
        self.title_entry = tk.Entry(self, font=("Microsoft YaHei", 11))
        self.title_entry.pack(fill="x", **padding)
        
        # 描述
        tk.Label(self, text="描述 (可选):", font=("Microsoft YaHei", 10)).pack(anchor="w", **padding)
        self.desc_text = tk.Text(self, height=3, font=("Microsoft YaHei", 10))
        self.desc_text.pack(fill="x", **padding)
        
        # 提醒时间
        tk.Label(self, text="提醒时间:", font=("Microsoft YaHei", 10)).pack(anchor="w", **padding)
        
        time_frame = tk.Frame(self)
        time_frame.pack(fill="x", **padding)
        
        # 日期
        now = datetime.now()
        self.date_entry = tk.Entry(time_frame, font=("Microsoft YaHei", 10), width=12)
        self.date_entry.pack(side="left", padx=(0, 5))
        self.date_entry.insert(0, now.strftime("%Y-%m-%d"))
        
        tk.Label(time_frame, text="时间:", font=("Microsoft YaHei", 10)).pack(side="left", padx=(10, 5))
        
        # 时间选择
        self.hour_var = tk.StringVar(value=now.strftime("%H"))
        self.minute_var = tk.StringVar(value="00")
        
        hours = [f"{h:02d}" for h in range(24)]
        minutes = [f"{m:02d}" for m in range(0, 60, 5)]
        
        ttk.Combobox(time_frame, textvariable=self.hour_var, values=hours, width=4, state="readonly").pack(side="left")
        tk.Label(time_frame, text=":", font=("Microsoft YaHei", 10)).pack(side="left")
        ttk.Combobox(time_frame, textvariable=self.minute_var, values=minutes, width=4, state="readonly").pack(side="left")
        
        # 重复选项
        tk.Label(self, text="重复:", font=("Microsoft YaHei", 10)).pack(anchor="w", **padding)
        self.repeat_var = tk.StringVar(value="none")
        repeat_frame = tk.Frame(self)
        repeat_frame.pack(fill="x", padx=15)

        repeats = [
            ("不重复", "none"),
            ("每天", "daily"),
            ("每周", "weekly"),
            ("每月", "monthly")
        ]
        for text, value in repeats:
            tk.Radiobutton(repeat_frame, text=text, variable=self.repeat_var, value=value,
                          font=("Microsoft YaHei", 9)).pack(side="left", padx=(0, 15))

        # 提前提醒设置
        tk.Label(self, text="提前提醒:", font=("Microsoft YaHei", 10)).pack(anchor="w", **padding)
        delay_frame = tk.Frame(self)
        delay_frame.pack(fill="x", padx=15)

        self.delay_var = tk.IntVar(value=30)
        delay_options = [(0, "不提前"), (10, "10分钟前"), (30, "30分钟前"), (60, "1小时前")]
        for minutes, text in delay_options:
            tk.Radiobutton(delay_frame, text=text, variable=self.delay_var, value=minutes,
                          font=("Microsoft YaHei", 9)).pack(side="left", padx=(0, 15))

        # 音乐设置（固定为 Taylor Swift）
        tk.Label(self, text="提醒音乐 🎵", font=("Microsoft YaHei", 10)).pack(anchor="w", **padding)
        music_frame = tk.Frame(self, bg="#f5f5f5")
        music_frame.pack(fill="x", padx=15, pady=5)
        tk.Label(music_frame, text="Taylor Swift - You Belong With Me", font=("Microsoft YaHei", 10),
                bg="#f5f5f5", fg="#666", padx=10, pady=8).pack(anchor="w")
        self.sound_entry = tk.Entry(sound_frame, textvariable=self.sound_path_var,
                                   font=("Microsoft YaHei", 9), width=20, state="disabled")
        self.sound_entry.pack(side="left", padx=5)

        tk.Button(sound_frame, text="选择文件", command=self.select_sound_file,
                 font=("Microsoft YaHei", 9)).pack(side="left")

        # 按钮
        btn_frame = tk.Frame(self)
        btn_frame.pack(fill="x", pady=20)

        tk.Button(btn_frame, text="取消", command=self.destroy, font=("Microsoft YaHei", 10),
                 width=10).pack(side="right", padx=15)
        tk.Button(btn_frame, text="保存", command=self.save, font=("Microsoft YaHei", 10),
                 width=10, bg="#4CAF50", fg="white").pack(side="right", padx=5)
    
    def fill_data(self):
        """填充编辑数据"""
        self.title_entry.insert(0, self.task.title)
        self.desc_text.insert("1.0", self.task.description)
        if self.task.due_time:
            date_part, time_part = self.task.due_time.split()
            self.date_entry.delete(0, tk.END)
            self.date_entry.insert(0, date_part)
            hour, minute = time_part.split(":")
            self.hour_var.set(hour)
            self.minute_var.set(minute)
        if self.task.repeat:
            self.repeat_var.set(self.task.repeat)
        if hasattr(self.task, 'delay_minutes'):
            self.delay_var.set(self.task.delay_minutes)
    
    def save(self):
        """保存任务"""
        title = self.title_entry.get().strip()
        if not title:
            messagebox.showerror("错误", "请输入任务标题")
            return
        
        description = self.desc_text.get("1.0", tk.END).strip()
        
        # 构建时间字符串
        date_str = self.date_entry.get().strip()
        try:
            datetime.strptime(date_str, "%Y-%m-%d")  # 验证日期格式
            due_time = f"{date_str} {self.hour_var.get()}:{self.minute_var.get()}"
        except ValueError:
            messagebox.showerror("错误", "日期格式不正确，请使用 YYYY-MM-DD 格式")
            return
        
        repeat = self.repeat_var.get()
        if repeat == "none":
            repeat = None
        
        # 默认使用 Taylor Swift - You Belong With Me
        default_sound = "Taylor Swift - You Belong With Me.mp3"

        self.result = {
            "title": title,
            "description": description,
            "due_time": due_time,
            "repeat": repeat,
            "delay_minutes": self.delay_var.get(),
            "sound_file": default_sound
        }
        self.destroy()


class RememberApp:
    """Remember 主应用程序"""
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Remember - 你的提醒助手")
        self.root.geometry("600x550")
        self.root.minsize(500, 400)
        
        # 设置图标（如果有的话）
        # self.root.iconbitmap("icon.ico")
        
        # 初始化任务管理器
        self.task_manager = TaskManager()
        
        # 创建界面
        self.create_widgets()
        
        # 启动提醒线程（三种提醒方式）
        self.reminder_thread = ReminderThread(
            self.task_manager,
            on_popup=self.show_reminder,      # 弹窗提醒
            on_sound=self.play_alert_sound,   # 声音提醒
            on_message=self.show_alert_message # 消息提醒
        )
        self.reminder_thread.start()
        
        # 刷新任务列表
        self.refresh_task_list()
        
        # 窗口关闭处理
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def create_widgets(self):
        """创建界面组件"""
        # 顶部标题栏（带灯泡图案）
        header = tk.Frame(self.root, bg="#FFF9E6", height=70)
        header.pack(fill="x", padx=0, pady=0)
        header.pack_propagate(False)

        # 灯泡图案和标题
        title_frame = tk.Frame(header, bg="#FFF9E6")
        title_frame.pack(expand=True)

        # 使用 Canvas 绘制简单灯泡
        bulb_canvas = tk.Canvas(title_frame, width=40, height=50, bg="#FFF9E6", highlightthickness=0)
        bulb_canvas.pack(side="left", padx=(0, 10))

        # 绘制灯泡（简单几何形状组合）
        # 灯泡玻璃部分（圆形）
        bulb_canvas.create_oval(8, 5, 32, 35, fill="#FFD93D", outline="#F5A623", width=2)
        # 灯泡底部螺纹
        bulb_canvas.create_rectangle(12, 35, 28, 40, fill="#999", outline="#666", width=1)
        bulb_canvas.create_rectangle(12, 40, 28, 45, fill="#999", outline="#666", width=1)
        # 高光
        bulb_canvas.create_oval(12, 10, 20, 18, fill="#FFF", outline="")

        # 标题文字
        tk.Label(title_frame, text="Remember", font=("Microsoft YaHei", 20, "bold"),
                bg="#FFF9E6", fg="#333").pack(side="left")
        tk.Label(title_frame, text="记住重要的事", font=("Microsoft YaHei", 11),
                bg="#FFF9E6", fg="#666").pack(side="left", padx=(10, 0), pady=5)

        # 顶部工具栏
        toolbar = tk.Frame(self.root, bg="#f0f0f0", height=50)
        toolbar.pack(fill="x", padx=10, pady=10)
        toolbar.pack_propagate(False)

        # 添加按钮
        self.add_btn = tk.Button(toolbar, text="+ 新建任务", command=self.add_task,
                                font=("Microsoft YaHei", 11), bg="#4CAF50", fg="white",
                                padx=15, pady=5, cursor="hand2")
        self.add_btn.pack(side="left", padx=5)
        
        # 筛选标签
        self.filter_var = tk.StringVar(value="pending")
        filter_frame = tk.Frame(toolbar, bg="#f0f0f0")
        filter_frame.pack(side="right", padx=5)
        
        tk.Radiobutton(filter_frame, text="待办", variable=self.filter_var, value="pending",
                      command=self.refresh_task_list, bg="#f0f0f0", font=("Microsoft YaHei", 10)).pack(side="left", padx=5)
        tk.Radiobutton(filter_frame, text="已完成", variable=self.filter_var, value="completed",
                      command=self.refresh_task_list, bg="#f0f0f0", font=("Microsoft YaHei", 10)).pack(side="left", padx=5)
        tk.Radiobutton(filter_frame, text="全部", variable=self.filter_var, value="all",
                      command=self.refresh_task_list, bg="#f0f0f0", font=("Microsoft YaHei", 10)).pack(side="left", padx=5)
        
        # 任务列表区域
        list_frame = tk.Frame(self.root)
        list_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # 创建树形列表
        columns = ("time", "title")
        self.task_tree = ttk.Treeview(list_frame, columns=columns, show="tree", selectmode="browse")
        
        # 设置列
        self.task_tree.column("#0", width=30, stretch=False)
        self.task_tree.column("time", width=120, anchor="w")
        self.task_tree.column("title", width=400, anchor="w")
        
        # 滚动条
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.task_tree.yview)
        self.task_tree.configure(yscrollcommand=scrollbar.set)
        
        self.task_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # 绑定双击编辑
        self.task_tree.bind("<Double-1>", self.on_task_double_click)
        
        # 底部状态栏
        self.status_bar = tk.Label(self.root, text="就绪", bd=1, relief=tk.SUNKEN, anchor="w",
                                  font=("Microsoft YaHei", 9))
        self.status_bar.pack(side="bottom", fill="x")
        
        # 右键菜单
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="编辑", command=self.edit_selected_task)
        self.context_menu.add_command(label="完成", command=self.complete_selected_task)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="删除", command=self.delete_selected_task)
        
        self.task_tree.bind("<Button-3>", self.show_context_menu)
    
    def refresh_task_list(self):
        """刷新任务列表"""
        # 清空列表
        for item in self.task_tree.get_children():
            self.task_tree.delete(item)
        
        # 获取筛选后的任务
        filter_type = self.filter_var.get()
        if filter_type == "pending":
            tasks = self.task_manager.get_pending_tasks()
            status_text = f"待办任务: {len(tasks)} 个"
        elif filter_type == "completed":
            tasks = self.task_manager.get_completed_tasks()
            status_text = f"已完成: {len(tasks)} 个"
        else:
            tasks = self.task_manager.tasks
            status_text = f"全部任务: {len(tasks)} 个"
        
        # 按时间排序
        tasks.sort(key=lambda t: t.due_time or "9999")
        
        # 添加到列表
        now = datetime.now()
        for task in tasks:
            # 选择图标
            if task.completed:
                icon = "✓"
                tag = "completed"
            elif task.due_time and datetime.strptime(task.due_time, "%Y-%m-%d %H:%M") < now:
                icon = "⚠"
                tag = "overdue"
            else:
                icon = "○"
                tag = "pending"
            
            # 格式化时间显示
            if task.due_time:
                try:
                    due = datetime.strptime(task.due_time, "%Y-%m-%d %H:%M")
                    if due.date() == now.date():
                        time_str = f"今天 {due.strftime('%H:%M')}"
                    elif due.date() == (now + timedelta(days=1)).date():
                        time_str = f"明天 {due.strftime('%H:%M')}"
                    else:
                        time_str = due.strftime('%m-%d %H:%M')
                except:
                    time_str = task.due_time
            else:
                time_str = "无时间"
            
            display_title = task.title
            if task.repeat:
                repeat_icons = {"daily": "🔄", "weekly": "📅", "monthly": "📆"}
                display_title = f"{repeat_icons.get(task.repeat, '')} {task.title}"

            # 显示提前提醒信息
            if hasattr(task, 'delay_minutes') and task.delay_minutes > 0:
                display_title += f"  (提前{task.delay_minutes}分钟)"

            item = self.task_tree.insert("", "end", text=icon, values=(time_str, display_title), tags=(tag,))
            self.task_tree.item(item, tags=(tag, task.id))
        
        # 设置标签样式
        self.task_tree.tag_configure("completed", foreground="gray")
        self.task_tree.tag_configure("overdue", foreground="red")
        self.task_tree.tag_configure("pending", foreground="black")
        
        self.status_bar.config(text=status_text)
    
    def add_task(self):
        """添加新任务"""
        dialog = AddTaskDialog(self.root)
        self.root.wait_window(dialog)
        
        if dialog.result:
            task = Task(**dialog.result)
            if self.task_manager.add_task(task):
                self.refresh_task_list()
                messagebox.showinfo("成功", "任务已添加！")
    
    def edit_selected_task(self):
        """编辑选中的任务"""
        selection = self.task_tree.selection()
        if not selection:
            return
        
        item = selection[0]
        tags = self.task_tree.item(item, "tags")
        if len(tags) < 2:
            return
        
        task_id = tags[1]
        task = next((t for t in self.task_manager.tasks if t.id == task_id), None)
        
        if task:
            dialog = AddTaskDialog(self.root, task)
            self.root.wait_window(dialog)
            
            if dialog.result:
                self.task_manager.update_task(task_id, **dialog.result)
                self.refresh_task_list()
    
    def complete_selected_task(self):
        """标记任务为完成"""
        selection = self.task_tree.selection()
        if not selection:
            return
        
        item = selection[0]
        tags = self.task_tree.item(item, "tags")
        if len(tags) < 2:
            return
        
        task_id = tags[1]
        task = next((t for t in self.task_manager.tasks if t.id == task_id), None)
        
        if task:
            new_status = not task.completed
            self.task_manager.update_task(task_id, completed=new_status)
            self.refresh_task_list()
    
    def delete_selected_task(self):
        """删除选中的任务"""
        selection = self.task_tree.selection()
        if not selection:
            return
        
        if messagebox.askyesno("确认", "确定要删除这个任务吗？"):
            item = selection[0]
            tags = self.task_tree.item(item, "tags")
            if len(tags) >= 2:
                task_id = tags[1]
                self.task_manager.delete_task(task_id)
                self.refresh_task_list()
    
    def on_task_double_click(self, event):
        """双击任务"""
        self.edit_selected_task()
    
    def show_context_menu(self, event):
        """显示右键菜单"""
        item = self.task_tree.identify_row(event.y)
        if item:
            self.task_tree.selection_set(item)
            self.context_menu.post(event.x_root, event.y_root)
    
    def show_reminder(self, task):
        """显示提醒"""
        # 在主线程中显示提醒
        self.root.after(0, lambda: self._show_reminder_dialog(task))
    
    def _show_reminder_dialog(self, task):
        """显示提醒对话框"""
        # 播放提示音
        self._play_sound(task.sound_file)

        # 显示提醒窗口
        reminder_window = tk.Toplevel(self.root)
        reminder_window.title("💡 任务提醒")
        reminder_window.geometry("350x260")
        reminder_window.transient(self.root)
        reminder_window.grab_set()

        # 置顶
        reminder_window.attributes("-topmost", True)

        # 提醒窗口中的灯泡图案
        bulb_canvas = tk.Canvas(reminder_window, width=50, height=60, highlightthickness=0)
        bulb_canvas.pack(pady=10)
        bulb_canvas.create_oval(10, 5, 40, 45, fill="#FFD93D", outline="#F5A623", width=2)
        bulb_canvas.create_rectangle(15, 45, 35, 52, fill="#999", outline="#666", width=1)
        bulb_canvas.create_rectangle(15, 52, 35, 59, fill="#999", outline="#666", width=1)
        bulb_canvas.create_oval(15, 10, 25, 22, fill="#FFF", outline="")

        tk.Label(reminder_window, text=f"该做任务了！", font=("Microsoft YaHei", 14, "bold")).pack()

        # 显示原定时间和实际提醒时间
        time_frame = tk.Frame(reminder_window)
        time_frame.pack(pady=5)
        if task.due_time:
            tk.Label(time_frame, text=f"到期时间: {task.due_time}", font=("Microsoft YaHei", 10),
                    fg="gray").pack()
        actual_time = task.get_actual_reminder_time()
        if actual_time and task.delay_minutes > 0:
            tk.Label(time_frame, text=f"已提前 {task.delay_minutes} 分钟提醒",
                    font=("Microsoft YaHei", 10), fg="#4CAF50").pack()

        tk.Label(reminder_window, text=task.title, font=("Microsoft YaHei", 12), wraplength=300).pack(pady=10)

        if task.description:
            tk.Label(reminder_window, text=task.description, font=("Microsoft YaHei", 10),
                    wraplength=300, fg="gray").pack()

        btn_frame = tk.Frame(reminder_window)
        btn_frame.pack(pady=15)

        def mark_done():
            self.task_manager.update_task(task.id, completed=True)
            self.refresh_task_list()
            reminder_window.destroy()

        def remind_later():
            # 10分钟后再次提醒
            new_time = (datetime.now() + timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M")
            self.task_manager.update_task(task.id, due_time=new_time)
            self.refresh_task_list()
            reminder_window.destroy()

        tk.Button(btn_frame, text="已完成", command=mark_done, bg="#4CAF50", fg="white",
                 font=("Microsoft YaHei", 10), padx=15).pack(side="left", padx=5)
        tk.Button(btn_frame, text="稍后提醒", command=remind_later,
                 font=("Microsoft YaHei", 10), padx=15).pack(side="left", padx=5)

        # 居中
        reminder_window.update_idletasks()
        width = reminder_window.winfo_width()
        height = reminder_window.winfo_height()
        x = (reminder_window.winfo_screenwidth() // 2) - (width // 2)
        y = (reminder_window.winfo_screenheight() // 2) - (height // 2)
        reminder_window.geometry(f'{width}x{height}+{x}+{y}')

    def play_alert_sound(self, task, minutes_left):
        """播放声音提醒（10分钟内）- 自动响音乐"""
        # 播放提示音
        self._play_sound(task.sound_file)
        # 更新状态栏提示
        self.status_bar.config(text=f"🔔 任务「{task.title[:15]}...」还有{minutes_left}分钟！")
        # 显示视觉提示
        self._flash_window()

    def show_alert_message(self, task, minutes_left):
        """显示消息提醒（30分钟前）- 自动发消息"""
        message = f"📢 提醒：「{task.title}」将在{minutes_left}分钟后到期"
        self.status_bar.config(text=message[:50])

        # 系统通知
        try:
            self._send_system_notification(task.title, f"还有 {minutes_left} 分钟")
        except Exception as e:
            print(f"系统通知失败: {e}")

    def _send_system_notification(self, title, subtitle):
        """发送系统通知"""
        import platform
        system = platform.system()

        try:
            if system == "Darwin":  # macOS
                import subprocess
                subprocess.run([
                    'osascript', '-e',
                    f'display notification "{title}" with title "Remember 提醒" subtitle "{subtitle}" sound name "default"'
                ])
            elif system == "Windows":
                # Windows 使用 win10toast
                try:
                    from win10toast import ToastNotifier
                    toaster = ToastNotifier()
                    toaster.show_toast("Remember 提醒", f"{title}\n{subtitle}", duration=5)
                except:
                    pass
            else:  # Linux
                import subprocess
                subprocess.run([
                    'notify-send',
                    '-a', 'Remember',
                    '-t', '5000',
                    'Remember 提醒',
                    f"{title}\n{subtitle}"
                ])
        except Exception as e:
            print(f"通知发送失败: {e}")

    def _play_sound(self, sound_file=None):
        """播放提示音 - 支持自定义音乐"""
        import platform
        system = platform.system()

        try:
            # 如果设置了自定义铃声且文件存在
            if sound_file and os.path.exists(sound_file):
                if system == "Windows":
                    import winsound
                    winsound.PlaySound(sound_file, winsound.SND_FILENAME | winsound.SND_ASYNC)
                elif system == "Darwin":  # macOS
                    import subprocess
                    subprocess.Popen(["afplay", sound_file], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:  # Linux
                    import subprocess
                    subprocess.Popen(["paplay", sound_file], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                # 默认提示音
                if system == "Windows":
                    import winsound
                    winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
                elif system == "Darwin":
                    import subprocess
                    subprocess.run(['afplay', '/System/Library/Sounds/Glass.aiff'])
                else:
                    print("\a")  # 终端响铃
        except Exception as e:
            print(f"播放声音失败: {e}")

    def _flash_window(self):
        """窗口闪烁提醒"""
        try:
            self.root.attributes('-topmost', True)
            self.root.attributes('-topmost', False)
        except:
            pass
    
    def on_closing(self):
        """关闭窗口"""
        self.reminder_thread.stop()
        self.root.destroy()
    
    def run(self):
        """运行应用程序"""
        self.root.mainloop()


def main():
    """程序入口"""
    app = RememberApp()
    app.run()


if __name__ == "__main__":
    main()
