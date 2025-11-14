function Navbar({ onLoginClick, onRegisterClick }) {
  return (
    <nav className="bg-[#1a2332] border-b border-gray-700/50">
      <div className="max-w-7xl mx-auto px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo - PO LEWEJ */}
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-gradient-to-br from-pink-500 to-purple-600 rounded-lg flex items-center justify-center">
              <span className="text-white text-xl">🃏</span>
            </div>
            <span className="text-white font-bold text-xl">Miedziowe Karty</span>
          </div>

          {/* Menu - PO ŚRODKU */}
          <div className="hidden md:flex items-center gap-8 absolute left-1/2 transform -translate-x-1/2">
            <a href="#zasady" className="text-gray-300 hover:text-white transition-colors">
              Zasady
            </a>
            <a href="#gry" className="text-gray-300 hover:text-white transition-colors">
              Gry
            </a>
            <a href="#ranking" className="text-gray-300 hover:text-white transition-colors">
              Ranking
            </a>
          </div>

          {/* Buttons - PO PRAWEJ */}
          <div className="flex items-center gap-3">
            <button
              onClick={onLoginClick}
              className="px-5 py-2 text-gray-300 hover:text-white hover:bg-gray-700/50 rounded-lg transition-all font-medium"
            >
              Zaloguj się
            </button>
            <button
              onClick={onRegisterClick}
              className="px-5 py-2 bg-teal-600 hover:bg-teal-700 text-white rounded-lg transition-all font-medium shadow-lg"
            >
              Zarejestruj
            </button>
          </div>
        </div>
      </div>
    </nav>
  )
}

export default Navbar