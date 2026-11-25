"use client";

import React, { useEffect, useId, useRef, useState } from "react";
import { Key, Shield, CheckCircle2, X, Info, Eye, EyeOff } from "lucide-react";

interface ApiKeyModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const PROVIDERS = [
  { id: "gemini", storageKey: "BIORESEARCH_GEMINI_KEY", label: "Google Gemini API key", placeholder: "AIzaSy..." },
  { id: "openai", storageKey: "BIORESEARCH_OPENAI_KEY", label: "OpenAI API key", placeholder: "sk-..." },
  { id: "anthropic", storageKey: "BIORESEARCH_ANTHROPIC_KEY", label: "Anthropic API key", placeholder: "sk-ant-..." },
  { id: "groq", storageKey: "BIORESEARCH_GROQ_KEY", label: "Groq API key", placeholder: "gsk_..." },
] as const;

type KeyMap = Record<(typeof PROVIDERS)[number]["id"], string>;

function loadKeys(): KeyMap {
  const read = (key: string) => {
    try {
      return localStorage.getItem(key) || "";
    } catch {
      return "";
    }
  };
  return Object.fromEntries(PROVIDERS.map((p) => [p.id, read(p.storageKey)])) as KeyMap;
}

/** Wrapper keeps the form unmounted while closed, so it re-reads storage fresh every time it opens. */
export default function ApiKeyModal({ isOpen, onClose }: ApiKeyModalProps) {
  if (!isOpen) return null;
  return <ApiKeyForm onClose={onClose} />;
}

function ApiKeyForm({ onClose }: { onClose: () => void }) {
  const [keys, setKeys] = useState<KeyMap>(loadKeys);
  const [showKeys, setShowKeys] = useState(false);
  const [saved, setSaved] = useState(false);
  const [storageError, setStorageError] = useState(false);
  const titleId = useId();
  const firstInputRef = useRef<HTMLInputElement>(null);
  const closeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Focus the first field, close on Escape, lock background scroll while open.
  useEffect(() => {
    firstInputRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
      if (closeTimer.current) clearTimeout(closeTimer.current);
    };
  }, [onClose]);

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    try {
      PROVIDERS.forEach((p) => localStorage.setItem(p.storageKey, keys[p.id].trim()));
      setStorageError(false);
    } catch {
      setStorageError(true);
      return;
    }
    setSaved(true);
    closeTimer.current = setTimeout(onClose, 900);
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-md animate-fadeIn"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <form
        onSubmit={handleSave}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="relative w-full max-w-lg max-h-[calc(100dvh-2rem)] overflow-y-auto bg-[#18191E] border border-white/10 rounded-2xl shadow-2xl p-6 text-white"
      >
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-white/10">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-blue-600/20 border border-blue-500/30 flex items-center justify-center text-blue-400">
              <Key className="w-5 h-5" aria-hidden="true" />
            </div>
            <div>
              <h2 id={titleId} className="text-lg font-bold">AI provider keys</h2>
              <p className="text-xs text-slate-400">Optional. Saved in this browser only.</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/5 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Honest status note */}
        <div className="my-4 p-3 rounded-xl bg-blue-950/30 border border-blue-500/20 text-xs text-blue-100/90 flex items-start gap-2.5">
          <Info className="w-4 h-4 text-blue-400 shrink-0 mt-0.5" aria-hidden="true" />
          <p className="leading-relaxed">
            Literature search works without any keys. Keys saved here are not sent to the research
            backend yet, so they won&apos;t change results until LLM synthesis is connected.
          </p>
        </div>

        {/* Inputs */}
        <div className="space-y-3.5 my-4">
          <div className="flex justify-end -mb-2">
            <button
              type="button"
              onClick={() => setShowKeys((v) => !v)}
              className="text-[11px] text-slate-400 hover:text-slate-200 flex items-center gap-1 transition-colors"
              aria-pressed={showKeys}
            >
              {showKeys ? <EyeOff className="w-3 h-3" /> : <Eye className="w-3 h-3" />}
              {showKeys ? "Hide keys" : "Show keys"}
            </button>
          </div>

          {PROVIDERS.map((p, i) => (
            <div key={p.id}>
              <label htmlFor={`key-${p.id}`} className="text-xs font-semibold text-slate-300 block mb-1">
                {p.label}
              </label>
              <input
                id={`key-${p.id}`}
                ref={i === 0 ? firstInputRef : undefined}
                type={showKeys ? "text" : "password"}
                value={keys[p.id]}
                onChange={(e) => setKeys((prev) => ({ ...prev, [p.id]: e.target.value }))}
                placeholder={p.placeholder}
                autoComplete="off"
                spellCheck={false}
                className="w-full bg-[#121316] border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 transition-all font-mono"
              />
            </div>
          ))}
        </div>

        {storageError && (
          <p role="alert" className="text-xs text-red-400 mb-3">
            Couldn&apos;t save: this browser is blocking local storage.
          </p>
        )}

        {/* Footer */}
        <div className="pt-4 border-t border-white/10 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-1.5 text-xs text-slate-400">
            <Shield className="w-3.5 h-3.5 text-slate-500" aria-hidden="true" />
            <span>Stored unencrypted in localStorage</span>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-xs font-medium text-slate-400 hover:text-white rounded-lg hover:bg-white/5 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saved}
              className="px-5 py-2 text-xs font-semibold bg-blue-600 hover:bg-blue-500 text-white rounded-lg shadow-lg shadow-blue-600/30 transition-all flex items-center gap-1.5 disabled:opacity-90"
            >
              {saved ? (
                <>
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-300" aria-hidden="true" />
                  <span>Saved</span>
                </>
              ) : (
                <span>Save keys</span>
              )}
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}
