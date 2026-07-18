"use client";
import { useState, useCallback, useRef, useEffect } from "react";

export type MicState = "idle" | "requesting" | "active" | "error" | "denied";

export type AudioChunk = {
  id: string;
  data: ArrayBuffer;
  timestamp: number;
  durationMs: number;
  sampleRate: number;
  sequence: number;
};

type UseMicrophoneOptions = {
  sampleRate?: number;
  chunkDurationMs?: number;
  echoCancellation?: boolean;
  noiseSuppression?: boolean;
  autoGainControl?: boolean;
  onChunk?: (chunk: AudioChunk) => void;
  onStateChange?: (state: MicState) => void;
  onError?: (error: Error) => void;
  onAudioLevel?: (level: number) => void;
};

export function useMicrophone(options: UseMicrophoneOptions = {}) {
  const {
    sampleRate = 16000,
    chunkDurationMs = 100,
    echoCancellation = true,
    noiseSuppression = true,
    autoGainControl = true,
    onChunk,
    onStateChange,
    onError,
    onAudioLevel,
  } = options;

  const [micState, setMicState] = useState<MicState>("idle");
  const [audioLevel, setAudioLevel] = useState(0);
  const streamRef = useRef<MediaStream | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const seqRef = useRef(0);
  const animFrameRef = useRef<number>(0);

  const updateState = useCallback((s: MicState) => {
    setMicState(s);
    onStateChange?.(s);
  }, [onStateChange]);

  const startLevelMeter = useCallback(() => {
    const ctx = audioCtxRef.current;
    const analyser = analyserRef.current;
    if (!ctx || !analyser) return;

    const dataArray = new Uint8Array(analyser.frequencyBinCount);
    const loop = () => {
      analyser.getByteTimeDomainData(dataArray);
      let sum = 0;
      for (let i = 0; i < dataArray.length; i++) {
        const val = (dataArray[i] - 128) / 128;
        sum += val * val;
      }
      const rms = Math.sqrt(sum / dataArray.length);
      const db = 20 * Math.log10(Math.max(rms, 1e-6));
      const normalized = Math.max(0, Math.min(1, (db + 60) / 60));
      setAudioLevel(normalized);
      onAudioLevel?.(normalized);
      animFrameRef.current = requestAnimationFrame(loop);
    };
    loop();
  }, [onAudioLevel]);

  const request = useCallback(async () => {
    if (micState === "active") return;
    updateState("requesting");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: { ideal: sampleRate },
          echoCancellation,
          noiseSuppression,
          autoGainControl,
          channelCount: 1,
        },
      });
      streamRef.current = stream;

      const audioCtx = new AudioContext({ sampleRate });
      audioCtxRef.current = audioCtx;

      const source = audioCtx.createMediaStreamSource(stream);
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);
      analyserRef.current = analyser;
      startLevelMeter();

      // MediaRecorder with configurable chunk size
      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : "audio/webm";
      const recorder = new MediaRecorder(stream, {
        mimeType,
        audioBitsPerSecond: 32000,
      });
      recorderRef.current = recorder;

      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          const reader = new FileReader();
          reader.onloadend = () => {
            const buf = reader.result as ArrayBuffer;
            seqRef.current++;
            onChunk?.({
              id: `chunk_${Date.now()}_${seqRef.current}`,
              data: buf,
              timestamp: Date.now(),
              durationMs: chunkDurationMs,
              sampleRate,
              sequence: seqRef.current,
            });
          };
          reader.readAsArrayBuffer(event.data);
        }
      };

      recorder.onerror = (event) => {
        const err = new Error(`MediaRecorder error: ${(event as any).error?.message || "unknown"}`);
        onError?.(err);
        updateState("error");
      };

      recorder.start(chunkDurationMs);
      updateState("active");
    } catch (err) {
      const error = err as DOMException;
      if (error.name === "NotAllowedError" || error.name === "PermissionDeniedError") {
        updateState("denied");
      } else {
        updateState("error");
        onError?.(error instanceof Error ? error : new Error(String(err)));
      }
    }
  }, [micState, sampleRate, echoCancellation, noiseSuppression, autoGainControl, chunkDurationMs, onChunk, onError, updateState, startLevelMeter]);

  const stop = useCallback(() => {
    if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
    if (recorderRef.current && recorderRef.current.state !== "inactive") {
      recorderRef.current.stop();
    }
    streamRef.current?.getTracks().forEach((t) => t.stop());
    audioCtxRef.current?.close();
    streamRef.current = null;
    recorderRef.current = null;
    audioCtxRef.current = null;
    analyserRef.current = null;
    updateState("idle");
  }, [updateState]);

  const toggleMute = useCallback(() => {
    streamRef.current?.getAudioTracks().forEach((t) => {
      t.enabled = !t.enabled;
    });
  }, []);

  useEffect(() => {
    return () => {
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
      streamRef.current?.getTracks().forEach((t) => t.stop());
      audioCtxRef.current?.close();
    };
  }, []);

  return {
    state: micState,
    audioLevel,
    isActive: micState === "active",
    request,
    stop,
    toggleMute,
  };
}
