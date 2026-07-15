import type { SourceType } from "@/lib/api";

export const MAX_UPLOAD_BYTES = 100 * 1024 * 1024;
export const IMAGE_UPLOAD_EXTENSIONS = [".png", ".jpg", ".jpe", ".jpeg", ".jfif", ".webp", ".gif", ".bmp", ".tif", ".tiff", ".heic", ".heif", ".avif", ".ico"];
export const AUDIO_UPLOAD_EXTENSIONS = [".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac", ".webm"];
export const VIDEO_UPLOAD_EXTENSIONS = [".mp4", ".mov", ".mkv", ".avi", ".m4v", ".webm"];
export const BOOK_UPLOAD_EXTENSIONS = [".pdf", ".epub", ".docx"];
export const IMAGE_ACCEPT = [...IMAGE_UPLOAD_EXTENSIONS, "image/jpeg", "image/png", "image/*"].join(",");
export const AUDIO_ACCEPT = [...AUDIO_UPLOAD_EXTENSIONS, "audio/*"].join(",");
export const VIDEO_ACCEPT = [...VIDEO_UPLOAD_EXTENSIONS, "video/*"].join(",");

export function hasFileExtension(file: File, extensions: string[]) {
  const filename = file.name.toLowerCase();
  return extensions.some((extension) => filename.endsWith(extension));
}

export function isImageUpload(file: File) {
  return file.type.startsWith("image/") || hasFileExtension(file, IMAGE_UPLOAD_EXTENSIONS);
}

export function isAudioUpload(file: File) {
  return file.type.startsWith("audio/") || hasFileExtension(file, AUDIO_UPLOAD_EXTENSIONS);
}

export function isVideoUpload(file: File) {
  return file.type.startsWith("video/") || hasFileExtension(file, VIDEO_UPLOAD_EXTENSIONS);
}

export function sourceTypeFromUpload(file: File): SourceType {
  if (isImageUpload(file)) {
    return "image";
  }
  if (isAudioUpload(file)) {
    return "audio";
  }
  if (hasFileExtension(file, BOOK_UPLOAD_EXTENSIONS)) {
    return "book";
  }
  return "file";
}
