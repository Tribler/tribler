export interface MediaMetadata {
    duration: number;
    container: string;
    has_video: boolean;
    video_codec: string;
    video_tag: string;
    width: number;
    height: number;
    video_bitrate: number;
    fps: number;
    has_audio: boolean;
    audio_codec: string;
    audio_tag: string;
    audio_sample_rate: number;
    audio_channels: number;
    pix_fmt: string;
}
