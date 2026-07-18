"use client";
import { useEffect, useRef } from "react";

type VoiceVisualizerProps = {
  level: number;
  isSpeaking: boolean;
  isMuted?: boolean;
  barCount?: number;
  height?: number;
};

export function VoiceVisualizer({
  level,
  isSpeaking,
  isMuted = false,
  barCount = 32,
  height = 48,
}: VoiceVisualizerProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animRef = useRef<number>(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const draw = () => {
      const w = canvas.width;
      const h = canvas.height;
      ctx.clearRect(0, 0, w, h);

      const barWidth = (w / barCount) * 0.7;
      const gap = (w / barCount) * 0.3;
      const centerY = h / 2;

      for (let i = 0; i < barCount; i++) {
        const phase = (i / barCount) * Math.PI * 2;
        const activeLevel = isSpeaking ? level : 0.05;
        const variation = Math.sin(Date.now() / 200 + phase + i * 0.3) * 0.3 + 0.7;
        const amplitude = activeLevel * variation * (isSpeaking ? 1 : 0.4);

        const barHeight = Math.max(3, amplitude * (h * 0.7));
        const x = i * (barWidth + gap);
        const y = centerY - barHeight / 2;

        const gradient = ctx.createLinearGradient(x, y, x, y + barHeight);
        if (isMuted) {
          gradient.addColorStop(0, "rgba(239, 68, 68, 0.5)");
          gradient.addColorStop(1, "rgba(239, 68, 68, 0.1)");
        } else if (isSpeaking) {
          gradient.addColorStop(0, "rgba(59, 130, 246, 0.9)");
          gradient.addColorStop(0.5, "rgba(99, 102, 241, 0.7)");
          gradient.addColorStop(1, "rgba(59, 130, 246, 0.1)");
        } else {
          gradient.addColorStop(0, "rgba(75, 85, 99, 0.4)");
          gradient.addColorStop(1, "rgba(75, 85, 99, 0.1)");
        }

        ctx.fillStyle = gradient;
        ctx.beginPath();
        ctx.roundRect(x, y, barWidth, barHeight, 2);
        ctx.fill();
      }

      animRef.current = requestAnimationFrame(draw);
    };

    draw();
    return () => {
      if (animRef.current) cancelAnimationFrame(animRef.current);
    };
  }, [level, isSpeaking, isMuted, barCount, height]);

  return (
    <canvas
      ref={canvasRef}
      width={400}
      height={height}
      className="w-full rounded-lg"
      style={{ height }}
    />
  );
}
