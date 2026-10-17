import React, { useState, useRef, useEffect } from 'react';
import { Send, Sparkles, ChefHat, RotateCcw, MessageSquare, Bot, AlertCircle } from 'lucide-react';
import { aiApi } from '../../api/aiApi';
import { ChatMessage } from '../../types/ai';
import { usePantry } from '../../context/PantryContext';

interface RecipeChatBoxProps {
  recipeName: string;
  ingredients?: Array<string | { name: string; amount?: string; unit?: string }>;
  instructions?: Array<string | { step: string }>;
}

const PRESET_QUESTIONS = [
  '🌱 Vegetarian or vegan swap?',
  '⏱️ Air fryer cooking instructions?',
  '🍷 Best drink or wine pairing?',
  '❄️ How to store & reheat leftovers?',
  '🌶️ How to make this spicier?',
  '🥗 What side dish pairs well?',
];

export const RecipeChatBox: React.FC<RecipeChatBoxProps> = ({
  recipeName,
  ingredients,
  instructions,
}) => {
  const { activeAIProvider, activeModel, handleRateLimitedModels } = usePantry();

  const [messages, setMessages] = useState<ChatMessage[]>(() => [
    {
      id: 'init-1',
      role: 'assistant',
      content: `Hello! I'm your AI Sous-Chef for **${recipeName}**. Ask me anything—ingredient substitutions, cooking techniques, side dish pairings, or dietary adjustments! 👨‍🍳🍳`,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    },
  ]);

  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  const handleSendMessage = async (textToSend?: string) => {
    const text = (textToSend || inputMessage).trim();
    if (!text || isLoading) return;

    setChatError(null);
    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: text,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInputMessage('');
    setIsLoading(true);

    try {
      // Build history for context
      const history = messages
        .filter((m) => m.id !== 'init-1')
        .slice(-6)
        .map((m) => ({ role: m.role, content: m.content }));

      const res = await aiApi.askRecipeChat({
        recipe_name: recipeName,
        ingredients: ingredients,
        instructions: instructions,
        message: text,
        history: history,
        provider: activeAIProvider,
        model: activeModel,
      });

      if (res.rate_limited_models && res.rate_limited_models.length > 0) {
        handleRateLimitedModels(res.rate_limited_models);
      }

      const botMsg: ChatMessage = {
        id: `bot-${Date.now()}`,
        role: 'assistant',
        content: res.reply,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        modelUsed: res.model_used,
      };

      setMessages((prev) => [...prev, botMsg]);
    } catch (err: any) {
      setChatError('Failed to get answer from chef. Please try again.');
      const fallbackMsg: ChatMessage = {
        id: `bot-${Date.now()}`,
        role: 'assistant',
        content: `I'm currently having a quick kitchen moment! For ${recipeName}, make sure your pan is preheated and season with salt and fresh herbs to taste. Feel free to ask another question!`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages((prev) => [...prev, fallbackMsg]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleClearChat = () => {
    setMessages([
      {
        id: `init-${Date.now()}`,
        role: 'assistant',
        content: `Chef chat cleared! Ask me anything about cooking **${recipeName}**!`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      },
    ]);
    setChatError(null);
  };

  // Simple markdown renderer for bold and lists
  const renderFormattedContent = (content: string) => {
    const lines = content.split('\n');
    return (
      <div className="space-y-1.5 text-sm leading-relaxed">
        {lines.map((line, idx) => {
          const trimmed = line.trim();
          if (!trimmed) return <div key={idx} className="h-1" />;

          // Bullet points
          if (trimmed.startsWith('* ') || trimmed.startsWith('- ') || trimmed.startsWith('• ')) {
            const textPart = trimmed.substring(2);
            return (
              <div key={idx} className="flex items-start gap-2 pl-2">
                <span className="text-amber-500 font-bold mt-0.5">•</span>
                <span>{renderInlineStyles(textPart)}</span>
              </div>
            );
          }

          // Numbered list
          const numMatch = trimmed.match(/^(\d+)\.\s+(.*)/);
          if (numMatch) {
            return (
              <div key={idx} className="flex items-start gap-2 pl-2">
                <span className="text-amber-600 font-bold text-xs mt-0.5">{numMatch[1]}.</span>
                <span>{renderInlineStyles(numMatch[2])}</span>
              </div>
            );
          }

          return <p key={idx}>{renderInlineStyles(trimmed)}</p>;
        })}
      </div>
    );
  };

  const renderInlineStyles = (text: string) => {
    // Bold matching **text**
    const parts = text.split(/(\*\*.*?\*\*)/g);
    return parts.map((part, i) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        return (
          <strong key={i} className="font-bold text-stone-900">
            {part.slice(2, -2)}
          </strong>
        );
      }
      return part;
    });
  };

  return (
    <section className="mt-12 rounded-3xl bg-white border border-stone-200/90 shadow-xl overflow-hidden">
      {/* Header */}
      <div className="bg-linear-to-r/srgb from-stone-900 via-stone-850 to-stone-900 px-6 py-4 text-white flex flex-wrap items-center justify-between gap-3 border-b border-stone-800">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-2xl bg-linear-to-br/srgb from-amber-400 to-brand-500 flex items-center justify-center shadow-md">
            <ChefHat className="w-5 h-5 text-stone-950" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="font-extrabold text-base tracking-tight text-white">
                AI Sous-Chef Kitchen Assistant
              </h3>
              <span className="inline-flex items-center gap-1 text-[10px] uppercase font-black px-2 py-0.5 rounded-full bg-amber-400/20 text-amber-300 border border-amber-400/30">
                <Sparkles className="w-2.5 h-2.5" /> Interactive
              </span>
            </div>
            <p className="text-xs text-stone-400 font-medium">
              Ask questions, customize ingredients, or get expert tips for <span className="text-stone-200 font-semibold">{recipeName}</span>
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="hidden sm:inline-flex items-center gap-1 text-xs text-stone-400 bg-stone-800/80 px-2.5 py-1 rounded-xl border border-stone-700 font-mono text-[11px]">
            <Bot className="w-3 h-3 text-amber-400" />
            {activeAIProvider === 'gemini' ? activeModel : 'LM Studio Local'}
          </span>
          <button
            type="button"
            onClick={handleClearChat}
            className="p-1.5 rounded-xl hover:bg-stone-800 text-stone-400 hover:text-stone-200 transition-colors cursor-pointer"
            title="Reset conversation"
          >
            <RotateCcw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Preset suggestion pills */}
      <div className="bg-stone-50/80 px-6 py-2.5 border-b border-stone-200/80 flex items-center gap-2 overflow-x-auto">
        <span className="text-[11px] font-bold text-stone-400 uppercase tracking-wider whitespace-nowrap flex items-center gap-1">
          <MessageSquare className="w-3 h-3 text-stone-400" /> Quick Ask:
        </span>
        <div className="flex items-center gap-1.5 flex-nowrap">
          {PRESET_QUESTIONS.map((q, idx) => (
            <button
              key={idx}
              type="button"
              disabled={isLoading}
              onClick={() => handleSendMessage(q)}
              className="text-xs font-semibold px-3 py-1 rounded-full bg-white hover:bg-amber-50 text-stone-700 hover:text-amber-900 border border-stone-200/90 transition-all whitespace-nowrap cursor-pointer hover:border-amber-300 disabled:opacity-50"
            >
              {q}
            </button>
          ))}
        </div>
      </div>

      {/* Messages Area */}
      <div className="p-6 max-h-[420px] min-h-[220px] overflow-y-auto space-y-4 bg-stone-50/30">
        {messages.map((m) => {
          const isUser = m.role === 'user';
          return (
            <div
              key={m.id}
              className={`flex items-start gap-3 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}
            >
              {/* Avatar */}
              <div
                className={`w-8 h-8 rounded-xl flex items-center justify-center shrink-0 text-xs font-bold ${
 isUser
 ? 'bg-stone-900 text-amber-400'
 : 'bg-amber-100 text-stone-900 border border-amber-300'
 }`}
              >
                {isUser ? 'You' : <ChefHat className="w-4 h-4 text-stone-800" />}
              </div>

              {/* Message Bubble */}
              <div
                className={`max-w-[82%] rounded-2xl p-4 ${
 isUser
 ? 'bg-linear-to-r/srgb from-stone-900 to-stone-800 text-white'
 : 'bg-white border border-stone-200/90 text-stone-800'
 }`}
              >
                {isUser ? (
                  <p className="text-sm font-medium leading-relaxed">{m.content}</p>
                ) : (
                  renderFormattedContent(m.content)
                )}

                <div
                  className={`mt-2 flex items-center justify-between text-[10px] font-mono ${
 isUser ? 'text-stone-400' : 'text-stone-400'
 }`}
                >
                  <span>{m.timestamp}</span>
                  {m.modelUsed && (
                    <span className="text-amber-600/80 font-bold">⚡ {m.modelUsed}</span>
                  )}
                </div>
              </div>
            </div>
          );
        })}

        {/* Loading indicator */}
        {isLoading && (
          <div className="flex items-start gap-3">
            <div className="w-8 h-8 rounded-xl bg-amber-100 border border-amber-300 flex items-center justify-center shrink-0 animate-bounce">
              <ChefHat className="w-4 h-4 text-stone-800" />
            </div>
            <div className="bg-white border border-stone-200/90 rounded-2xl p-4 flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
              <div className="w-2 h-2 rounded-full bg-brand-500 animate-pulse delay-150" />
              <div className="w-2 h-2 rounded-full bg-stone-700 animate-pulse delay-300" />
              <span className="text-xs font-semibold text-stone-500 ml-2">
                Chef is preparing your culinary answer...
              </span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Error alert */}
      {chatError && (
        <div className="px-6 py-2 bg-red-50 border-t border-red-200 text-red-700 text-xs flex items-center gap-2">
          <AlertCircle className="w-3.5 h-3.5 shrink-0" />
          <span>{chatError}</span>
        </div>
      )}

      {/* Input area */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          handleSendMessage();
        }}
        className="p-4 bg-white border-t border-stone-200/90 flex items-center gap-2"
      >
        <input
          type="text"
          value={inputMessage}
          onChange={(e) => setInputMessage(e.target.value)}
          placeholder={`Ask anything about ${recipeName} (e.g., 'What can I substitute for garlic?')...`}
          className="flex-1 bg-stone-100/80 hover:bg-stone-100 focus:bg-white text-stone-900 text-sm rounded-2xl px-4 py-3 border border-stone-200 focus:border-stone-400 focus:outline-hidden transition-all placeholder:text-stone-400"
          disabled={isLoading}
        />
        <button
          type="submit"
          disabled={!inputMessage.trim() || isLoading}
          className="px-5 py-3 rounded-2xl bg-stone-900 hover:bg-stone-800 text-white font-bold text-sm shadow-md transition-all flex items-center gap-2 cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <span>Ask Chef</span>
          <Send className="w-4 h-4 text-amber-400" />
        </button>
      </form>
    </section>
  );
};
