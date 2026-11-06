import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import en from '../locales/en.json' with { type: 'json' }
import fil from '../locales/fil.json' with { type: 'json' }

const stored = localStorage.getItem('hris-lang')
const lng = stored === 'fil' || stored === 'en' ? stored : 'en'

void i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    fil: { translation: fil },
  },
  lng,
  fallbackLng: 'en',
  interpolation: { escapeValue: false },
})

document.documentElement.lang = lng === 'fil' ? 'fil' : 'en'

export function setLanguage(next: 'en' | 'fil') {
  localStorage.setItem('hris-lang', next)
  document.documentElement.lang = next === 'fil' ? 'fil' : 'en'
  void i18n.changeLanguage(next)
}

export default i18n
