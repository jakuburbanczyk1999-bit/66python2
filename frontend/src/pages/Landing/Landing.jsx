import { useState, useEffect } from 'react'
import Navbar from '../../components/Navbar'
import LoginModal from './LoginModal'
import RegisterModal from './RegisterModal'
import GuestModal from './GuestModal'

function Landing() {
  const [showLoginModal, setShowLoginModal] = useState(false)
  const [showRegisterModal, setShowRegisterModal] = useState(false)
  const [showGuestModal, setShowGuestModal] = useState(false)
  
  // Statystyki pobierane z API
  const [stats, setStats] = useState({
    activePlayers: 0,
    totalGames: 0,
    availableGames: 1
  })

  // Pobierz statystyki przy załadowaniu strony
  useEffect(() => {
    const fetchStats = async () => {
      try {
        const response = await fetch('/api/stats')
        if (response.ok) {
          const data = await response.json()
          setStats(data)
        }
      } catch (error) {
        console.log('Nie udało się pobrać statystyk')
      }
    }
    
    fetchStats()
    
    // Odświeżaj co 30 sekund
    const interval = setInterval(fetchStats, 30000)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="min-h-screen bg-[#1a2736]">
      {/* Navbar */}
      <Navbar 
        onLoginClick={() => setShowLoginModal(true)}
        onRegisterClick={() => setShowRegisterModal(true)}
      />

      {/* Hero Section */}
      <section className="relative py-20 px-4 overflow-hidden">
        {/* Floating Cards Background */}
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute top-20 right-[15%] w-20 h-28 bg-white/10 rounded-lg transform rotate-12 border border-white/20 shadow-2xl"></div>
          <div className="absolute top-40 right-[25%] w-16 h-24 bg-white/10 rounded-lg transform -rotate-6 border border-white/20 shadow-2xl"></div>
          <div className="absolute top-32 right-[8%] w-16 h-24 bg-white/10 rounded-lg transform rotate-45 border border-white/20 shadow-2xl"></div>
          <div className="absolute bottom-20 right-[20%] w-20 h-28 bg-white/10 rounded-lg transform -rotate-12 border border-white/20 shadow-2xl"></div>
        </div>

        <div className="max-w-7xl mx-auto relative z-10">
          {/* Title - BARDZIEJ W LEWO */}
          <div className="max-w-3xl">
            <h1 className="text-5xl md:text-7xl font-bold text-white mb-4">
              Witaj w świecie
              <br />
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-teal-400 to-cyan-400 inline-flex items-center gap-4">
                <img src="/icon.png" alt="Miedziowe Karty" className="w-12 h-12 md:w-16 md:h-16 inline-block" />
                Miedziowych Kart
              </span>
            </h1>

            {/* Description */}
            <p className="text-xl text-gray-300 mb-8 max-w-2xl leading-relaxed">
              Portal gier karcianych z rankingami, turniejami i powtórkami
              najlepszych rozgrywek. Graj online z przyjaciółmi lub rywalizuj z
              najlepszymi!
            </p>

            {/* Buttons */}
            <div className="flex flex-wrap gap-4 mb-12">
              <button
                onClick={() => setShowLoginModal(true)}
                className="px-8 py-4 bg-teal-600 hover:bg-teal-700 text-white rounded-lg transition-all font-semibold shadow-xl flex items-center gap-2"
              >
                <span>🎮</span>
                <span>Zacznij grać</span>
              </button>
              <button
                onClick={() => setShowGuestModal(true)}
                className="px-8 py-4 bg-gray-700/50 hover:bg-gray-700 text-white rounded-lg transition-all font-semibold border border-gray-600 flex items-center gap-2"
              >
                <span>👤</span>
                <span>Graj jako gość</span>
              </button>
            </div>

            {/* Stats - dynamiczne */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 max-w-2xl">
              <div className="text-center sm:text-left">
                <div className="text-4xl font-bold text-teal-400 mb-1">{(stats?.activePlayers || 0).toLocaleString()}</div>
                <div className="text-sm text-gray-400">Aktywnych graczy</div>
              </div>
              <div className="text-center sm:text-left">
                <div className="text-4xl font-bold text-teal-400 mb-1">{(stats?.totalGames || 0).toLocaleString()}</div>
                <div className="text-sm text-gray-400">Rozegranych gier</div>
              </div>
              <div className="text-center sm:text-left">
                <div className="text-4xl font-bold text-teal-400 mb-1">{stats?.availableGames || 1}</div>
                <div className="text-sm text-gray-400">Dostępne gry</div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Games Section */}
      <section id="gry" className="py-16 px-4 bg-[#1e2a3a]">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-4xl font-bold text-white mb-3">Dostępne Gry</h2>
            <p className="text-gray-400">Wybierz grę i rozpocznij rozgrywkę!</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Gra w 66 */}
            <div className="bg-[#243447] border border-gray-700/50 rounded-xl p-6 hover:border-teal-500/50 transition-all">
              <div className="mb-4">
                <div className="w-16 h-16 bg-gradient-to-br from-teal-500 to-cyan-500 rounded-lg flex items-center justify-center text-3xl mb-4">
                  🃏
                </div>
                <div className="inline-block px-3 py-1 bg-teal-500/20 text-teal-400 text-xs font-semibold rounded-full mb-3">
                  Dostępne
                </div>
              </div>
              <h3 className="text-2xl font-bold text-white mb-3">Gra w 66</h3>
              <p className="text-gray-400 mb-4 leading-relaxed">
                Klasyczna gra karciana dla 3-4 graczy. Zbieraj lewy, zdobywaj punkty i osiągnij 66 aby wygrać rozdanie!
              </p>
              <div className="flex flex-wrap gap-3 mb-4 text-sm">
                <span className="text-gray-500 flex items-center gap-1">
                  <span>👥</span> 3-4 graczy
                </span>
                <span className="text-gray-500 flex items-center gap-1">
                  <span>⏱️</span> ~15 min
                </span>
                <span className="text-gray-500 flex items-center gap-1">
                  <span>🏆</span> Rankingowa
                </span>
              </div>
              <button 
                onClick={() => setShowLoginModal(true)}
                className="w-full py-3 bg-teal-600 hover:bg-teal-700 text-white rounded-lg transition-all font-semibold"
              >
                Zagraj teraz →
              </button>
            </div>

            {/* Tysiąc */}
            <div className="bg-[#243447] border border-gray-700/50 rounded-xl p-6 hover:border-yellow-500/50 transition-all opacity-75">
              <div className="mb-4">
                <div className="w-16 h-16 bg-gradient-to-br from-red-500 to-pink-500 rounded-lg flex items-center justify-center text-3xl mb-4">
                  🎴
                </div>
                <div className="inline-block px-3 py-1 bg-yellow-500/20 text-yellow-400 text-xs font-semibold rounded-full mb-3">
                  ⏳ Wkrótce
                </div>
              </div>
              <h3 className="text-2xl font-bold text-white mb-3">Tysiąc</h3>
              <p className="text-gray-400 mb-4 leading-relaxed">
                Popularna polska gra karciana. Licytuj, zbieraj lewy i osiągnij 1000 punktów!
              </p>
              <div className="flex flex-wrap gap-3 mb-4 text-sm">
                <span className="text-gray-500 flex items-center gap-1">
                  <span>👥</span> 2-4 graczy
                </span>
                <span className="text-gray-500 flex items-center gap-1">
                  <span>⏱️</span> ~20 min
                </span>
                <span className="text-gray-500 flex items-center gap-1">
                  <span>🏆</span> Rankingowa
                </span>
              </div>
              <button disabled className="w-full py-3 bg-gray-700 text-gray-400 rounded-lg cursor-not-allowed font-semibold">
                Wkrótce dostępne
              </button>
            </div>

            {/* Pan */}
            <div className="bg-[#243447] border border-gray-700/50 rounded-xl p-6 hover:border-yellow-500/50 transition-all opacity-75">
              <div className="mb-4">
                <div className="w-16 h-16 bg-gradient-to-br from-amber-500 to-orange-500 rounded-lg flex items-center justify-center text-3xl mb-4">
                  👑
                </div>
                <div className="inline-block px-3 py-1 bg-yellow-500/20 text-yellow-400 text-xs font-semibold rounded-full mb-3">
                  ⏳ Wkrótce
                </div>
              </div>
              <h3 className="text-2xl font-bold text-white mb-3">Pan</h3>
              <p className="text-gray-400 mb-4 leading-relaxed">
                Dynamiczna gra karciana. Pozbywaj się kart i nie zostaw "Panem" z ostatnią kartą!
              </p>
              <div className="flex flex-wrap gap-3 mb-4 text-sm">
                <span className="text-gray-500 flex items-center gap-1">
                  <span>👥</span> 2-6 graczy
                </span>
                <span className="text-gray-500 flex items-center gap-1">
                  <span>⏱️</span> ~10 min
                </span>
                <span className="text-gray-500 flex items-center gap-1">
                  <span>🎯</span> Towarzyska
                </span>
              </div>
              <button disabled className="w-full py-3 bg-gray-700 text-gray-400 rounded-lg cursor-not-allowed font-semibold">
                Wkrótce dostępne
              </button>
            </div>

            {/* Remik */}
            <div className="bg-[#243447] border border-gray-700/50 rounded-xl p-6 hover:border-yellow-500/50 transition-all opacity-75">
              <div className="mb-4">
                <div className="w-16 h-16 bg-gradient-to-br from-emerald-500 to-green-500 rounded-lg flex items-center justify-center text-3xl mb-4">
                  🍀
                </div>
                <div className="inline-block px-3 py-1 bg-yellow-500/20 text-yellow-400 text-xs font-semibold rounded-full mb-3">
                  ⏳ Wkrótce
                </div>
              </div>
              <h3 className="text-2xl font-bold text-white mb-3">Remik</h3>
              <p className="text-gray-400 mb-4 leading-relaxed">
                Klasyczna gra w układanie sekwensów i grup. Zbieraj karty i wykładaj kombinacje!
              </p>
              <div className="flex flex-wrap gap-3 mb-4 text-sm">
                <span className="text-gray-500 flex items-center gap-1">
                  <span>👥</span> 2-4 graczy
                </span>
                <span className="text-gray-500 flex items-center gap-1">
                  <span>⏱️</span> ~30 min
                </span>
                <span className="text-gray-500 flex items-center gap-1">
                  <span>🏆</span> Rankingowa
                </span>
              </div>
              <button disabled className="w-full py-3 bg-gray-700 text-gray-400 rounded-lg cursor-not-allowed font-semibold">
                Wkrótce dostępne
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20 px-4 bg-[#1a5a52] border-t border-teal-900/50">
        <div className="max-w-4xl mx-auto text-center">
          <h2 className="text-4xl md:text-5xl font-bold text-white mb-4">
            Gotowy do gry?
          </h2>
          <p className="text-xl text-gray-200 mb-8">
            Dołącz do graczy i rozpocznij swoją przygodę z Miedziowymi Kartami!
          </p>
          <button
            onClick={() => setShowRegisterModal(true)}
            className="px-10 py-4 bg-teal-600 hover:bg-teal-700 text-white text-lg rounded-lg transition-all font-semibold shadow-2xl"
          >
            Zarejestruj się za darmo
          </button>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-[#1a2332] border-t border-gray-700/50 py-8 px-4">
        <div className="max-w-6xl mx-auto text-center">
          <div className="flex items-center justify-center gap-3 mb-3">
            <img src="/icon.png" alt="Miedziowe Karty" className="w-8 h-8" />
            <span className="text-white font-bold text-xl">Miedziowe Karty</span>
          </div>
          <p className="text-gray-400 text-sm">
            Portal gier karcianych online. Graj, rywalizuj, rozwijaj się!
          </p>
        </div>
      </footer>

      {/* Modals */}
      {showLoginModal && (
        <LoginModal onClose={() => setShowLoginModal(false)} />
      )}
      {showRegisterModal && (
        <RegisterModal onClose={() => setShowRegisterModal(false)} />
      )}
      {showGuestModal && (
        <GuestModal onClose={() => setShowGuestModal(false)} />
      )}
    </div>
  )
}

export default Landing
