import React, { useState } from 'react';
import { Sparkles, Bot, ChevronDown, Check, AlertTriangle } from 'lucide-react';
import { usePantry } from '../../context/PantryContext';
import { AIProvider } from '../../types/ai';

export const AIProviderSwitcher: React.FC<{ compact?: boolean }> = ({ compact }) => {
  const {
    activeAIProvider,
    setActiveAIProvider,
    activeModel,
    setActiveModel,
    availableModels,
    rateLimitedModels,
    aiProvidersInfo,
  } = usePantry();

  const [modelDropdownOpen, setModelDropdownOpen] = useState(false);

  const isLMStudioOnline = Boolean(aiProvidersInfo?.lmstudio_online);
  const geminiModel = activeModel || aiProvidersInfo?.gemini_model || 'gemini-3.5-flash-lite';
  const lmModel = aiProvidersInfo?.lmstudio_model || 'Local Model';

  const currentModelDisplay =
    availableModels.find((m) => m.id === activeModel)?.displayName ||
    availableModels.find((m) => m.id === activeModel)?.name ||
    activeModel;

  return (
    <div className="flex flex-wrap items-center gap-2">
      <div
        className={`inline-flex items-center gap-1 p-1 rounded-2xl bg-stone-100/90 border border-stone-200/80 ${
 compact ? 'text-xs' : 'text-sm'
 }`}
      >
        {/* Cloud AI Button */}
        <button
          type="button"
          onClick={() => setActiveAIProvider('gemini')}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl font-bold transition-all cursor-pointer ${
 activeAIProvider === 'gemini'
 ? 'bg-white text-stone-900'
 : 'text-stone-500 hover:text-stone-900'
 }`}
          title={`Cloud AI Engine (${geminiModel})`}
        >
          <Sparkles className="w-3.5 h-3.5 text-brand-500" />
          <span>Cloud AI</span>
        </button>

        {/* Local AI Button (LM Studio) */}
        <button
          type="button"
          onClick={() => {
            if (isLMStudioOnline) {
              setActiveAIProvider('lmstudio');
            }
          }}
          disabled={!isLMStudioOnline}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl font-bold transition-all relative ${
 !isLMStudioOnline
 ? 'opacity-40 cursor-not-allowed text-stone-400 bg-stone-100'
 : activeAIProvider === 'lmstudio'
 ? 'bg-white text-stone-900 cursor-pointer'
 : 'text-stone-500 hover:text-stone-900 cursor-pointer'
 }`}
          title={
            isLMStudioOnline
              ? `Local AI Engine (${lmModel}) - Ready`
              : `Local AI Offline: Launch LM Studio on port 1234 to enable (${lmModel})`
          }
        >
          <Bot className={`w-3.5 h-3.5 ${isLMStudioOnline ? 'text-teal-600' : 'text-stone-400'}`} />
          <span>Local AI</span>
          {!isLMStudioOnline && (
            <span className="text-[9px] px-1 py-0.2 rounded-md bg-stone-200 text-stone-500 font-extrabold uppercase tracking-wide">
              Offline
            </span>
          )}
        </button>
      </div>

      {/* Model Selection Dropdown (Only when Cloud AI is active) */}
      {activeAIProvider === 'gemini' && availableModels.length > 0 && (
        <div className="relative">
          <button
            type="button"
            onClick={() => setModelDropdownOpen(!modelDropdownOpen)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-2xl bg-stone-900/85 hover:bg-stone-900 text-stone-200 text-xs font-semibold border border-stone-700/80 cursor-pointer transition-colors"
          >
            <span className="text-[10px] text-amber-400 font-black uppercase tracking-wider">Model:</span>
            <span className="truncate max-w-[140px] font-mono text-[11px]">
              {currentModelDisplay}
            </span>
            <ChevronDown className="w-3 h-3 text-stone-400" />
          </button>

          {modelDropdownOpen && (
            <>
              <div
                className="fixed inset-0 z-40"
                onClick={() => setModelDropdownOpen(false)}
              />
              <div className="fixed left-1/2 -translate-x-1/2 top-24 w-[min(18rem,calc(100vw-1.5rem))] max-h-96 overflow-y-auto bg-stone-900 border border-stone-700 rounded-2xl shadow-2xl z-50 p-2 space-y-1 sm:absolute sm:left-auto sm:right-0 sm:top-auto sm:translate-x-0 sm:mt-1.5 sm:w-72">
                <div className="px-2.5 py-1 text-[10px] font-black uppercase tracking-wider text-stone-400 flex items-center justify-between">
                  <span>Google Gemini Models</span>
                  <span className="text-[9px] text-amber-400/80 lowercase">auto-fallback active</span>
                </div>
                {availableModels.map((m) => {
                  const isRateLimited = rateLimitedModels.includes(m.id);
                  const isSelected = activeModel === m.id;
                  const label = m.displayName || m.name || m.id;

                  return (
                    <button
                      key={m.id}
                      type="button"
                      disabled={isRateLimited}
                      onClick={() => {
                        if (!isRateLimited) {
                          setActiveModel(m.id);
                          setModelDropdownOpen(false);
                        }
                      }}
                      className={`w-full text-left px-3 py-2 rounded-xl text-xs flex items-center justify-between transition-all ${
 isRateLimited
 ? 'opacity-40 bg-stone-800/40 text-stone-500 cursor-not-allowed border border-dashed border-stone-700/50'
 : isSelected
 ? 'bg-brand-500 text-white font-bold cursor-pointer'
 : 'text-stone-300 hover:bg-stone-800 cursor-pointer'
 }`}
                      title={
                        isRateLimited
                          ? `${label} reached rate/quota limit. Auto-fallback will use other available models.`
                          : m.description || label
                      }
                    >
                      <div className="min-w-0 pr-2">
                        <div className="flex items-center gap-1.5">
                          <span className="font-semibold truncate">{label}</span>
                          {isRateLimited && (
                            <span className="inline-flex items-center gap-0.5 text-[9px] px-1.5 py-0.5 rounded-sm bg-red-900/60 text-red-300 font-bold border border-red-800/50">
                              <AlertTriangle className="w-2.5 h-2.5" /> Limit
                            </span>
                          )}
                        </div>
                        {m.description && (
                          <div className={`text-[10px] truncate ${isSelected ? 'text-amber-100' : 'text-stone-400'}`}>
                            {m.description}
                          </div>
                        )}
                      </div>
                      {isSelected && <Check className="w-3.5 h-3.5 shrink-0 text-white" />}
                    </button>
                  );
                })}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
};


