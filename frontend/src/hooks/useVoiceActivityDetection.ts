"use client";
import { useState, useRef, useCallback, useEffect } from "react";

type VADState = "silence" | "speaking" | "transitioning";

type UseVADOptions = {
  silenceTimeoutMs?: number;
  activationThreshold?: number;
  deactivationThreshold?: number;
  minSpeechDurationMs?: number;
  onSpeechStart?: () => void;
  onSpeechEnd?: (durationMs: number) => void;
  onSilenceStart?: () => void;
};

export function useVoiceActivityDetection(options: UseVADOptions = {}) {
  const {
    silenceTimeoutMs = 1500,
    activationThreshold = 0.15,
    deactivationThreshold = 0.08,
    minSpeechDurationMs = 300,
    onSpeechStart,
    onSpeechEnd,
    onSilenceStart,
  } = options;

  const [vadState, setVadState] = useState<VADState>("silence");
  const [isSpeaking, setIsSpeaking] = useState(false);

  const speechStartRef = useRef(0);
  const silenceStartRef = useRef(0);
  const currentLevelRef = useRef(0);
  const timerRef = useRef<ReturnType<typeof setInterval>>();

  const processAudioLevel = useCallback((level: number) => {
    currentLevelRef.current = level;

    if (vadState === "silence" && level > activationThreshold) {
      speechStartRef.current = Date.now();
      setVadState("transitioning");
      setIsSpeaking(true);
      onSpeechStart?.();
    }

    if (vadState === "speaking" && level < deactivationThreshold) {
      silenceStartRef.current = Date.now();
      setVadState("transitioning");
    }

    if (vadState === "transitioning" && level > activationThreshold) {
      const recordDuration = Date.now() - speechStartRef.current;
      if (recordDuration >= minSpeechDurationMs) {
        setVadState("speaking");
        setIsSpeaking(true);
      }
    }
  }, [vadState, activationThreshold, deactivationThreshold, minSpeechDurationMs, onSpeechStart]);

  useEffect(() => {
    timerRef.current = setInterval(() => {
      const now = Date.now();
      if (vadState === "transitioning" && currentLevelRef.current < deactivationThreshold) {
        const silenceDuration = now - silenceStartRef.current;
        if (silenceDuration > silenceTimeoutMs) {
          setVadState("silence");
          setIsSpeaking(false);
          onSilenceStart?.();
          const speechDuration = now - speechStartRef.current;
          if (speechDuration > minSpeechDurationMs) {
            onSpeechEnd?.(speechDuration);
          }
        }
      }
    }, 100);

    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [vadState, deactivationThreshold, silenceTimeoutMs, minSpeechDurationMs, onSpeechEnd, onSilenceStart]);

  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);

  return {
    vadState,
    isSpeaking,
    processAudioLevel,
  };
}
