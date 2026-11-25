// clipfix: give TIFF-only image clipboards a PNG copy, the way macOS's own
// screenshots do. Built for Monosnap 7, whose ⌘C writes only public.tiff, so
// apps that turn a pasted image into a file hand over a huge .tiff instead of a .png.
//
// It only rewrites a clipboard that holds nothing but a TIFF (plus the
// org.nspasteboard.source tag Monosnap adds), so text, rich content and
// password-manager copies are never touched.
//
// Install (builds it and starts it at login):
//   curl -fsSL https://tools.michaelwarkentin.com/macos/install-clipfix.sh | bash
// Or build it yourself and run it in a terminal to try it:
//   swiftc -O -swift-version 5 clipfix.swift -o ~/.local/bin/clipfix

import AppKit

let pasteboard = NSPasteboard.general
let pngType = NSPasteboard.PasteboardType.png    // public.png
let tiffType = NSPasteboard.PasteboardType.tiff  // public.tiff
let legacyTIFFType = NSPasteboard.PasteboardType("NeXT TIFF v4.0 pasteboard type")
let sourceType = NSPasteboard.PasteboardType("org.nspasteboard.source")
let rewritable: Set<NSPasteboard.PasteboardType> = [tiffType, legacyTIFFType, sourceType]
let maxTIFFBytes = 200_000_000  // skip giant images rather than stall on them

var lastChangeCount = pasteboard.changeCount

func logLine(_ message: String) {
    FileHandle.standardError.write(Data("\(Date()) clipfix: \(message)\n".utf8))
}

func addPNGIfTIFFOnly() {
    guard let types = pasteboard.types,
          types.contains(tiffType),
          !types.contains(pngType),
          Set(types).isSubset(of: rewritable),
          let tiff = pasteboard.data(forType: tiffType),
          tiff.count <= maxTIFFBytes,
          let png = NSBitmapImageRep(data: tiff)?.representation(using: .png, properties: [:])
    else { return }

    let source = pasteboard.data(forType: sourceType)

    // Something new was copied while we were encoding: leave it alone.
    guard pasteboard.changeCount == lastChangeCount else { return }

    let item = NSPasteboardItem()
    item.setData(png, forType: pngType)  // PNG first, TIFF as fallback, like macOS screenshots
    item.setData(tiff, forType: tiffType)
    if let source { item.setData(source, forType: sourceType) }

    pasteboard.clearContents()
    let ok = pasteboard.writeObjects([item])
    lastChangeCount = pasteboard.changeCount

    let app = source.map { String(decoding: $0, as: UTF8.self) }.flatMap { $0.isEmpty ? nil : $0 } ?? "an unknown app"
    logLine(ok ? "added a \(png.count / 1024) KB PNG next to a \(tiff.count / 1024) KB TIFF from \(app)"
               : "couldn't write to the clipboard")
}

let timer = Timer(timeInterval: 0.25, repeats: true) { _ in
    let current = pasteboard.changeCount
    guard current != lastChangeCount else { return }
    lastChangeCount = current
    addPNGIfTIFFOnly()
}
RunLoop.main.add(timer, forMode: .common)
logLine("watching the clipboard")
RunLoop.main.run()
