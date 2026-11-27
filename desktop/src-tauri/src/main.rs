#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::Serialize;
use tauri::{
    menu::{MenuBuilder, MenuItemBuilder},
    tray::TrayIconBuilder,
    Manager,
};

#[derive(Serialize)]
struct DesktopStatus {
    product: &'static str,
    version: &'static str,
    hotkeys: [&'static str; 2],
    wake_word: &'static str,
}

#[tauri::command]
fn get_desktop_status() -> DesktopStatus {
    DesktopStatus {
        product: "NOVA Tauri Shell",
        version: "2.0.0",
        hotkeys: ["Ctrl+Shift+N", "Ctrl+Shift+M"],
        wake_word: "Hey Nova",
    }
}

#[tauri::command]
fn trigger_nova_voice(transcript: String) -> String {
    format!("NOVA voice dispatcher queued transcript: {}", transcript)
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_notification::init())
        .plugin(tauri_plugin_global_shortcut::Builder::new().build())
        .setup(|app| {
            let open_item = MenuItemBuilder::with_id("open", "Open Aspirant AI").build(app)?;
            let quit_item = MenuItemBuilder::with_id("quit", "Quit NOVA").build(app)?;
            let menu = MenuBuilder::new(app).items(&[&open_item, &quit_item]).build()?;

            let _tray = TrayIconBuilder::new()
                .menu(&menu)
                .on_menu_event(|app, event| match event.id().as_ref() {
                    "open" => {
                        if let Some(window) = app.get_webview_window("main") {
                            let _ = window.show();
                            let _ = window.set_focus();
                        }
                    }
                    "quit" => app.exit(0),
                    _ => {}
                })
                .build(app)?;
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![get_desktop_status, trigger_nova_voice])
        .run(tauri::generate_context!())
        .expect("error running Aspirant AI Tauri shell");
}
