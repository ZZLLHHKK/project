from __future__ import annotations

import tkinter as tk
from tkinter import scrolledtext
from tkinter import ttk
from tkinter.font import Font
from typing import Callable


def create_popup_shell(
    parent: tk.Misc,
    *,
    safe_title: str,
    heading_text: str,
    heading_font: Font,
    geometry: str,
    padding: int = 10,
    resizable: tuple[bool, bool] = (True, True),
) -> tuple[tk.Toplevel, ttk.Frame]:
    win = tk.Toplevel(parent)
    win.title(safe_title)
    win.wm_title(safe_title)
    win.geometry(geometry)
    win.resizable(*resizable)

    outer = ttk.Frame(win, padding=padding)
    outer.pack(fill=tk.BOTH, expand=True)

    heading = tk.Label(outer, text=heading_text, anchor="w", font=heading_font, fg="#0f172a")
    heading.pack(fill=tk.X, pady=(0, 10))
    return win, outer


def create_panel_popup(
    parent: tk.Misc,
    *,
    safe_title: str,
    heading_text: str,
    heading_font: Font,
    button_font: Font,
    geometry: str,
    refresh_label: str,
    on_refresh: Callable[[ttk.Frame], None],
    padding: int = 10,
    resizable: tuple[bool, bool] = (True, True),
) -> tuple[tk.Toplevel, ttk.Frame]:
    win, outer = create_popup_shell(
        parent,
        safe_title=safe_title,
        heading_text=heading_text,
        heading_font=heading_font,
        geometry=geometry,
        padding=padding,
        resizable=resizable,
    )

    content_frame = ttk.Frame(outer)
    content_frame.pack(fill=tk.BOTH, expand=True)
    on_refresh(content_frame)

    tk.Button(
        outer,
        text=refresh_label,
        font=button_font,
        command=lambda: on_refresh(content_frame),
    ).pack(pady=(10, 0))
    return win, content_frame


def create_text_popup(
    parent: tk.Misc,
    *,
    safe_title: str,
    heading_text: str,
    heading_font: Font,
    body_font: Font,
    button_font: Font,
    geometry: str,
    refresh_label: str,
    initial_content: str,
    on_refresh: Callable[[], str],
    padding: int = 10,
    resizable: tuple[bool, bool] = (True, True),
) -> tuple[tk.Toplevel, tk.Text]:
    win, outer = create_popup_shell(
        parent,
        safe_title=safe_title,
        heading_text=heading_text,
        heading_font=heading_font,
        geometry=geometry,
        padding=padding,
        resizable=resizable,
    )

    text = scrolledtext.ScrolledText(
        outer,
        wrap=tk.WORD,
        font=body_font,
        bg="#ffffff",
        fg="#0f172a",
        relief=tk.SOLID,
        bd=1,
        padx=10,
        pady=8,
    )
    text.pack(fill=tk.BOTH, expand=True)

    heading_font = body_font.copy()
    heading_font.configure(weight="bold")
    text.tag_configure("heading", font=heading_font, foreground="#0f172a", spacing1=4, spacing3=4)
    text.tag_configure("bullet", foreground="#1e293b", lmargin1=14, lmargin2=22, spacing3=2)
    text.tag_configure("body", foreground="#334155", spacing3=2)

    def _apply_tags() -> None:
        end_line = int(text.index("end-1c").split(".")[0])
        for line_no in range(1, end_line + 1):
            raw_line = text.get(f"{line_no}.0", f"{line_no}.end").strip()
            if not raw_line:
                continue
            if raw_line.startswith("-"):
                text.tag_add("bullet", f"{line_no}.0", f"{line_no}.end")
            elif raw_line.endswith(":") or line_no == 1:
                text.tag_add("heading", f"{line_no}.0", f"{line_no}.end")
            else:
                text.tag_add("body", f"{line_no}.0", f"{line_no}.end")

    text.insert("1.0", initial_content)
    _apply_tags()
    text.configure(state=tk.DISABLED)

    def _refresh() -> None:
        payload = on_refresh()
        text.configure(state=tk.NORMAL)
        text.delete("1.0", tk.END)
        text.insert("1.0", payload)
        _apply_tags()
        text.configure(state=tk.DISABLED)

    tk.Button(
        outer,
        text=refresh_label,
        font=button_font,
        bg="#ffffff",
        activebackground="#f1f5f9",
        command=_refresh,
    ).pack(pady=(8, 0))
    return win, text
