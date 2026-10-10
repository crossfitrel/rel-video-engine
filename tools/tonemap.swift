import AVFoundation
import Foundation

let a = CommandLine.arguments
guard a.count >= 3 else { print("usage: tonemap in out"); exit(2) }
let input = URL(fileURLWithPath: a[1])
let output = URL(fileURLWithPath: a[2])
try? FileManager.default.removeItem(at: output)

let asset = AVURLAsset(url: input)
// force synchronous load of tracks
let sem0 = DispatchSemaphore(value: 0)
var vtrack: AVAssetTrack? = nil
asset.loadTracks(withMediaType: .video) { tracks, _ in vtrack = tracks?.first; sem0.signal() }
sem0.wait()
guard let track = vtrack else { print("no video track"); exit(1) }

let natural = track.naturalSize
let t = track.preferredTransform
let rendered = natural.applying(t)
let rw = abs(rendered.width) < 1 ? natural.width : abs(rendered.width)
let rh = abs(rendered.height) < 1 ? natural.height : abs(rendered.height)

let vc = AVMutableVideoComposition(propertiesOf: asset)
vc.colorPrimaries = AVVideoColorPrimaries_ITU_R_709_2
vc.colorTransferFunction = AVVideoTransferFunction_ITU_R_709_2
vc.colorYCbCrMatrix = AVVideoYCbCrMatrix_ITU_R_709_2
if vc.renderSize.width < 1 || vc.renderSize.height < 1 {
    vc.renderSize = CGSize(width: rw, height: rh)
}
if vc.frameDuration.seconds <= 0 {
    vc.frameDuration = CMTime(value: 1, timescale: 30)
}

guard let ex = AVAssetExportSession(asset: asset, presetName: AVAssetExportPresetHighestQuality) else { print("no export"); exit(1) }
ex.outputURL = output
ex.outputFileType = .mov
ex.videoComposition = vc
let s = DispatchSemaphore(value: 0)
ex.exportAsynchronously { print("status", ex.status.rawValue); if let e = ex.error { print("err", e) }; s.signal() }
s.wait()
exit(ex.status == .completed ? 0 : 1)
