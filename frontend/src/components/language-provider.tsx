"use client";

import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { getTranslations, type Language, type TranslationKey } from "@/lib/i18n";

type LanguageContextValue = {
  language: Language;
  setLanguage: (language: Language) => void;
  toggleLanguage: () => void;
  t: Record<TranslationKey, string>;
};

const LanguageContext = createContext<LanguageContextValue | null>(null);

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<Language>("zh");

  useEffect(() => {
    const stored = window.localStorage.getItem("app-language");
    if (stored === "en" || stored === "zh") {
      setLanguageState(stored);
    }
  }, []);

  useEffect(() => {
    document.documentElement.lang = language === "zh" ? "zh-CN" : "en";
    window.localStorage.setItem("app-language", language);
  }, [language]);

  const value = useMemo<LanguageContextValue>(() => {
    const setLanguage = (nextLanguage: Language) => setLanguageState(nextLanguage);
    const toggleLanguage = () => setLanguageState((current) => (current === "zh" ? "en" : "zh"));

    return {
      language,
      setLanguage,
      toggleLanguage,
      t: getTranslations(language),
    };
  }, [language]);

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

export function useLanguage() {
  const context = useContext(LanguageContext);
  if (!context) {
    throw new Error("useLanguage must be used within LanguageProvider");
  }
  return context;
}
