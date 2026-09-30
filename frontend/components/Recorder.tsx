"use client";

import { useEffect, useRef, useState } from "react";
import { Mic, Square, Trash2, Upload } from "lucide-react";
import { getUserErrorMessage } from "../lib/api";

export default function Recorder({
  disabled,
  onUpload,
  onError
}: {
  disabled: boolean;
  onUpload: (blob: Blob) => Promise<void>;
  onError: (message: string) => void;
}) {
  const recorderRef = useRef<MediaRecorder | null>(null);
  const mountedRef = useRef(true);
  const chunksRef = useRef<Blob[]>([]);
  const [recording, setRecording] = useState(false);
  const [busy, setBusy] = useState(false);
  const [recordedBlob, setRecordedBlob] = useState<Blob | null>(null);
  const [previewUrl, setPreviewUrl] = useState("");
  const [seconds, setSeconds] = useState(0);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      const recorder = recorderRef.current;
      if (recorder) {
        recorder.onstop = null;
        if (recorder.state !== "inactive") recorder.stop();
        recorder.stream.getTracks().forEach((track) => track.stop());
      }
    };
  }, []);

  useEffect(() => {
    if (!recording) return;
    const timer = window.setInterval(() => setSeconds((value) => value + 1), 1000);
    return () => window.clearInterval(timer);
  }, [recording]);

  useEffect(() => () => { if (previewUrl) URL.revokeObjectURL(previewUrl); }, [previewUrl]);

  async function start() {
    if (!navigator.mediaDevices?.getUserMedia) {
      onError("Браузер не поддерживает запись с микрофона.");
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (!mountedRef.current) {
        stream.getTracks().forEach((track) => track.stop());
        return;
      }
      chunksRef.current = [];
      setSeconds(0);
      setRecordedBlob(null);
      const preferredType = [
        "audio/ogg;codecs=opus",
        "audio/webm;codecs=opus",
        "audio/webm"
      ].find((candidate) => MediaRecorder.isTypeSupported(candidate));
      const options = preferredType ? { mimeType: preferredType } : undefined;
      const recorder = new MediaRecorder(stream, options);
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunksRef.current.push(event.data);
        }
      };
      recorder.onstop = () => {
        const recordedType = recorder.mimeType || chunksRef.current[0]?.type || "audio/webm";
        const blob = new Blob(chunksRef.current, { type: recordedType });
        setRecordedBlob(blob);
        setPreviewUrl(URL.createObjectURL(blob));
        stream.getTracks().forEach((track) => track.stop());
      };
      recorder.start();
      recorderRef.current = recorder;
      setRecording(true);
    } catch {
      setBusy(false);
      setRecording(false);
      onError("Не удалось получить доступ к микрофону. Проверьте разрешение браузера и попробуйте снова.");
    }
  }

  function stop() {
    recorderRef.current?.stop();
    setRecording(false);
  }


  async function submitRecording() {
    if (!recordedBlob) return;
    setBusy(true);
    try {
      await onUpload(recordedBlob);
      setRecordedBlob(null);
      setPreviewUrl("");
    } catch (err) {
      onError(getUserErrorMessage(err, "Не удалось отправить запись. Попробуйте ещё раз."));
    } finally {
      setBusy(false);
    }
  }

  if (recording) {
    return <button className="danger" onClick={stop}><Square size={16} /> Остановить · {Math.floor(seconds / 60)}:{String(seconds % 60).padStart(2, "0")}</button>;
  }
  if (recordedBlob && previewUrl) {
    return (
      <div className="recording-preview">
        <audio controls src={previewUrl} />
        <span>{Math.floor(seconds / 60)}:{String(seconds % 60).padStart(2, "0")}</span>
        <button className="ghost" type="button" onClick={() => { setRecordedBlob(null); setPreviewUrl(""); }}><Trash2 size={15} /> Перезаписать</button>
        <button className="secondary" type="button" disabled={busy} onClick={submitRecording}><Upload size={15} /> {busy ? "Отправляем…" : "Отправить запись"}</button>
      </div>
    );
  }
  return (
    <button className="secondary" disabled={disabled || busy} onClick={start}>
      {busy ? <Upload size={16} /> : <Mic size={16} />} {busy ? "Отправляем" : "Записать ответ"}
    </button>
  );
}

