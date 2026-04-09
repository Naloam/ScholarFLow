import { useTranslation } from "react-i18next";

export function LanguageSwitcher() {
  const { i18n } = useTranslation();
  const isZh = i18n.language.startsWith("zh");

  return (
    <button
      type="button"
      className="meta-chip language-switcher"
      onClick={() => void i18n.changeLanguage(isZh ? "en" : "zh")}
      data-testid="language-switcher"
      title={isZh ? "Switch to English" : "切换到中文"}
    >
      {isZh ? "EN" : "中文"}
    </button>
  );
}
