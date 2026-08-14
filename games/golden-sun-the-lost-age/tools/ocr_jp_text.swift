#!/usr/bin/env swift

import Foundation
import ImageIO
import Vision

func loadPGM(_ url: URL) -> CGImage? {
    guard let data = try? Data(contentsOf: url) else { return nil }
    let bytes = [UInt8](data)
    var cursor = 0

    func readToken() -> String? {
        while cursor < bytes.count {
            if bytes[cursor] == 35 {
                while cursor < bytes.count && bytes[cursor] != 10 { cursor += 1 }
            } else if bytes[cursor] == 9 || bytes[cursor] == 10 || bytes[cursor] == 13 || bytes[cursor] == 32 {
                cursor += 1
            } else {
                break
            }
        }
        let start = cursor
        while cursor < bytes.count && ![9, 10, 13, 32].contains(bytes[cursor]) { cursor += 1 }
        guard cursor > start else { return nil }
        return String(bytes: bytes[start..<cursor], encoding: .ascii)
    }

    guard
        readToken() == "P5",
        let widthToken = readToken(), let width = Int(widthToken),
        let heightToken = readToken(), let height = Int(heightToken),
        readToken() == "255"
    else { return nil }

    while cursor < bytes.count && [9, 10, 13, 32].contains(bytes[cursor]) { cursor += 1 }
    guard cursor + width * height <= bytes.count else { return nil }
    let pixels = data.subdata(in: cursor..<(cursor + width * height)) as CFData
    guard let provider = CGDataProvider(data: pixels) else { return nil }
    return CGImage(
        width: width,
        height: height,
        bitsPerComponent: 8,
        bitsPerPixel: 8,
        bytesPerRow: width,
        space: CGColorSpaceCreateDeviceGray(),
        bitmapInfo: CGBitmapInfo(rawValue: CGImageAlphaInfo.none.rawValue),
        provider: provider,
        decode: nil,
        shouldInterpolate: false,
        intent: .defaultIntent
    )
}

func loadImage(_ path: String) -> CGImage? {
    let url = URL(fileURLWithPath: path)
    if url.pathExtension.lowercased() == "pgm" {
        return loadPGM(url)
    }
    guard let source = CGImageSourceCreateWithURL(url as CFURL, nil) else { return nil }
    return CGImageSourceCreateImageAtIndex(source, 0, nil)
}

guard CommandLine.arguments.count >= 2 else {
    fputs("usage: ocr_jp_text.swift IMAGE.png...\n", stderr)
    exit(2)
}

for path in CommandLine.arguments.dropFirst() {
    guard let image = loadImage(path) else {
        fputs("cannot read image: \(path)\n", stderr)
        continue
    }

    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.recognitionLanguages = ["ja-JP"]
    request.usesLanguageCorrection = false

    do {
        try VNImageRequestHandler(cgImage: image).perform([request])
        let lines = (request.results ?? []).compactMap {
            $0.topCandidates(1).first?.string
        }
        print("\(path)\t\(lines.joined(separator: "\\n"))")
    } catch {
        fputs("OCR failed for \(path): \(error)\n", stderr)
    }
}
