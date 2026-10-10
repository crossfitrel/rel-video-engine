// vision_ocr.swift — OCR מקומי של macOS (Vision) על פריימים מווידאו. v9.32 (23.9.26)
// שימוש: swift vision_ocr.swift <video> <n_frames> [--langs he,en] | --list-langs
// פלט: JSON {"duration":..,"frames":[{"t":..,"obs":[{"text","conf","box":[x,y,w,h]}]}]}
// box מנורמל 0..1, מקור בפינה השמאלית-עליונה (הפוך מ-Vision).
import Foundation
import AVFoundation
import Vision

func out(_ o: Any) {
    let d = try! JSONSerialization.data(withJSONObject: o, options: [])
    FileHandle.standardOutput.write(d)
    FileHandle.standardOutput.write("\n".data(using: .utf8)!)
}

let args = CommandLine.arguments
if args.count >= 2 && args[1] == "--list-langs" {
    let r = VNRecognizeTextRequest()
    r.recognitionLevel = .accurate
    out(["langs": (try? r.supportedRecognitionLanguages()) ?? []])
    exit(0)
}
guard args.count >= 3, let n = Int(args[2]) else {
    FileHandle.standardError.write("usage: vision_ocr.swift <video> <n> [--langs he,en]\n".data(using: .utf8)!)
    exit(2)
}
var langs = ["he", "en"]
if let i = args.firstIndex(of: "--langs"), i + 1 < args.count {
    langs = args[i + 1].split(separator: ",").map(String.init)
}
let asset = AVURLAsset(url: URL(fileURLWithPath: args[1]))
let dur = CMTimeGetSeconds(asset.duration)
let gen = AVAssetImageGenerator(asset: asset)
gen.appliesPreferredTrackTransform = true
gen.requestedTimeToleranceBefore = .zero
gen.requestedTimeToleranceAfter = .zero
var frames: [[String: Any]] = []
for k in 0..<max(1, n) {
    let t = dur * (0.1 + 0.8 * Double(k) / Double(max(1, n - 1)))
    guard let img = try? gen.copyCGImage(at: CMTime(seconds: t, preferredTimescale: 600), actualTime: nil) else { continue }
    let req = VNRecognizeTextRequest()
    req.recognitionLevel = .accurate
    req.usesLanguageCorrection = false
    req.recognitionLanguages = langs
    // עברית אינה בשפות ה-OCR של Vision (macOS 27: נבדק --list-langs) ⇒ גילוי אזורי
    // טקסט בלתי-תלוי-שפה (VNDetectTextRectanglesRequest) הוא האות לבירול עם כיתוב צרוב.
    let rq = VNDetectTextRectanglesRequest()
    rq.reportCharacterBoxes = true
    try? VNImageRequestHandler(cgImage: img, options: [:]).perform([req, rq])
    var rects: [[String: Any]] = []
    for o in (rq.results ?? []) {
        let b = o.boundingBox
        rects.append(["box": [Double(b.origin.x), Double(1 - b.origin.y - b.height), Double(b.width), Double(b.height)],
                      "conf": Double(o.confidence), "chars": o.characterBoxes?.count ?? 0])
    }
    var obs: [[String: Any]] = []
    for o in (req.results ?? []) {
        guard let c = o.topCandidates(1).first else { continue }
        let b = o.boundingBox
        obs.append(["text": c.string, "conf": Double(c.confidence),
                    "box": [Double(b.origin.x), Double(1 - b.origin.y - b.height), Double(b.width), Double(b.height)]])
    }
    frames.append(["t": t, "obs": obs, "rects": rects])
}
out(["duration": dur, "frames": frames])
