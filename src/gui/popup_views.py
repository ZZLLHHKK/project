from __future__ import annotations

import tkinter as tk
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

    heading = tk.Label(outer, text=heading_text, anchor="w", font=heading_font)
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

    text = tk.Text(outer, wrap=tk.WORD, font=body_font)
    text.pack(fill=tk.BOTH, expand=True)
    text.insert("1.0", initial_content)
    text.configure(state=tk.DISABLED)

    def _refresh() -> None:
        payload = on_refresh()
        text.configure(state=tk.NORMAL)
        text.delete("1.0", tk.END)
        text.insert("1.0", payload)
        text.configure(state=tk.DISABLED)

    tk.Button(
        outer,
        text=refresh_label,
        font=button_font,
        command=_refresh,
    ).pack(pady=(8, 0))
    return win, text
