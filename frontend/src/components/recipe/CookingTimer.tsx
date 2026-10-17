import React, { useState, useEffect, useRef } from 'react';
import { Play, Pause, RotateCcw, Plus, Bell, Volume2, VolumeX, Flame } from 'lucide-react';
import confetti from 'canvas-confetti';
import { StyledButton } from '../common/StyledButton';

interface CookingTimerProps {
  initialMinutes?: number;
  label?: string;
}

export const CookingTimer: React.FC<CookingTimerProps> = ({
  initialMinutes = 15,
  label = 'Step Timer',
}) => {
  const [totalSeconds, setTotalSeconds] = useState(initialMinutes * 60);
  const [timeLeft, setTimeLeft] = useState(initialMinutes * 60);
  const [isRunning, setIsRunning] = useState(false);
  const [soundEnabled, setSoundEnabled] = useState(true);

  const timerRef = useRef<NodeJS.Timeout | null>(null);

  // Play sound when timer finishes
  const playChime = () => {
    if (!soundEnabled) return;
    try {
      const audioCtx = new (window.AudioContext || (window as any).webkitAudioContext)();
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();

      osc.type = 'sine';
      osc.frequency.setValueAtTime(587.33, audioCtx.currentTime); // D5
      osc.frequency.exponentialRampToValueAtTime(880, audioCtx.currentTime + 0.3); // A5

      gain.gain.setValueAtTime(0.3, audioCtx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.8);

      osc.connect(gain);
      gain.connect(audioCtx.destination);

      osc.start();
      osc.stop(audioCtx.currentTime + 0.8);
    } catch (e) {
      console.log('Audio chime not supported');
    }
  };

  useEffect(() => {
    if (isRunning) {
      timerRef.current = setInterval(() => {
        setTimeLeft((prev) => {
          if (prev <= 1) {
            clearInterval(timerRef.current!);
            setIsRunning(false);
            playChime();
            confetti({
              particleCount: 80,
              spread: 70,
              origin: { y: 0.7 },
            });
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
    } else if (timerRef.current) {
      clearInterval(timerRef.current);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [isRunning, soundEnabled]);

  const toggleTimer = () => {
    if (timeLeft === 0) {
      setTimeLeft(totalSeconds);
    }
    setIsRunning(!isRunning);
  };

  const resetTimer = () => {
    setIsRunning(false);
    setTimeLeft(totalSeconds);
  };

  const addTime = (seconds: number) => {
    setTimeLeft((prev) => prev + seconds);
    setTotalSeconds((prev) => prev + seconds);
  };

  const minutes = Math.floor(timeLeft / 60);
  const seconds = timeLeft % 60;
  const progressPercent = totalSeconds > 0 ? ((totalSeconds - timeLeft) / totalSeconds) * 100 : 100;

  return (
    <div className="bg-white rounded-3xl p-6 border border-stone-200 shadow-xs flex flex-col items-center">
      <div className="w-full flex items-center justify-between mb-4">
        <div className="flex items-center gap-2 text-stone-800 font-bold text-sm">
          <Flame className="w-4 h-4 text-brand-500" />
          <span>{label}</span>
        </div>
        <button
          onClick={() => setSoundEnabled(!soundEnabled)}
          className="text-stone-400 hover:text-stone-700 transition-colors p-1"
          title={soundEnabled ? 'Mute Chime' : 'Unmute Chime'}
        >
          {soundEnabled ? <Volume2 className="w-4 h-4 text-emerald-600" /> : <VolumeX className="w-4 h-4" />}
        </button>
      </div>

      {/* Circular Progress Ring with Digital Time */}
      <div className="relative w-44 h-44 flex items-center justify-center my-2">
        <svg className="w-full h-full transform -rotate-90" viewBox="0 0 100 100">
          <circle
            cx="50"
            cy="50"
            r="42"
            className="stroke-stone-100"
            strokeWidth="6"
            fill="transparent"
          />
          <circle
            cx="50"
            cy="50"
            r="42"
            className="stroke-brand-500 transition-all duration-500 ease-linear"
            strokeWidth="6"
            strokeDasharray={264}
            strokeDashoffset={264 - (264 * progressPercent) / 100}
            strokeLinecap="round"
            fill="transparent"
          />
        </svg>

        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-3xl font-extrabold text-stone-900 tracking-tight font-mono">
            {String(minutes).padStart(2, '0')}:{String(seconds).padStart(2, '0')}
          </span>
          <span className="text-[11px] font-semibold text-stone-400 uppercase tracking-wider mt-0.5">
            {timeLeft === 0 ? '🎉 Ready!' : isRunning ? 'Cooking...' : 'Paused'}
          </span>
        </div>
      </div>

      {/* Main Controls */}
      <div className="flex items-center gap-3 mt-4 w-full justify-center">
        <StyledButton
          $variant={isRunning ? 'secondary' : 'primary'}
          $size="md"
          onClick={toggleTimer}
          className="min-w-[120px]"
        >
          {isRunning ? (
            <>
              <Pause className="w-4 h-4" /> Pause
            </>
          ) : (
            <>
              <Play className="w-4 h-4" /> {timeLeft === 0 ? 'Restart' : 'Start'}
            </>
          )}
        </StyledButton>

        <button
          onClick={resetTimer}
          className="p-2.5 rounded-xl border border-stone-200 text-stone-600 hover:bg-stone-100 transition-colors"
          title="Reset Timer"
        >
          <RotateCcw className="w-4 h-4" />
        </button>
      </div>

      {/* Quick Add Time Chips */}
      <div className="flex items-center gap-2 mt-4">
        <button
          onClick={() => addTime(60)}
          className="text-xs px-2.5 py-1 rounded-lg bg-stone-100 hover:bg-stone-200 text-stone-700 font-medium transition-colors flex items-center gap-0.5"
        >
          <Plus className="w-3 h-3" /> 1m
        </button>
        <button
          onClick={() => addTime(300)}
          className="text-xs px-2.5 py-1 rounded-lg bg-stone-100 hover:bg-stone-200 text-stone-700 font-medium transition-colors flex items-center gap-0.5"
        >
          <Plus className="w-3 h-3" /> 5m
        </button>
      </div>
    </div>
  );
};
