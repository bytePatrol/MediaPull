fn main() {
    // Force rebuild when frontend files change
    println!("cargo:rerun-if-changed=../dist");
    println!("cargo:rerun-if-changed=../index.html");
    println!("cargo:rerun-if-changed=../src");
    tauri_build::build()
}
