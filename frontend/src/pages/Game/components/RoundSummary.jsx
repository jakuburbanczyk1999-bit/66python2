function RoundSummary({ summary, onNextRound, loading, myTeam }) {
  // Sprawdź czy moja drużyna wygrała
  const didIWin = summary.wygrana_druzyna === myTeam;
  
  // Sprawdź typ kontraktu
  const isSoloContract = summary.kontrakt === 'LEPSZA' || summary.kontrakt === 'GORSZA';
  const isBezPytania = summary.kontrakt === 'BEZ_PYTANIA';
  
  // Określ czy pokazywać punkty w kartach
  const shouldShowCardPoints = !isSoloContract;
  
  return (
    <div className="absolute inset-0 flex items-center justify-center bg-black/70 backdrop-blur-sm rounded-[3rem]">
      <div className="bg-gray-900 rounded-xl p-8 max-w-lg border border-gray-700 shadow-2xl">
        <h2 className="text-2xl font-bold text-white mb-4 text-center">
          🎊 Rozdanie zakończone!
        </h2>
        
        {summary.powod && (
          <div className="mb-4 p-3 bg-blue-500/10 border border-blue-500/30 rounded-lg text-center">
            <p className="text-blue-300 text-sm">📌 {summary.powod}</p>
          </div>
        )}

        {/* Punkty w kartach - ukryj dla Lepsza/Gorsza */}
        {shouldShowCardPoints && summary.wynik_w_kartach && (
          <div className="mb-4">
            <h3 className="text-sm font-semibold text-gray-400 mb-2">🎴 Punkty w kartach:</h3>
            <div className="space-y-2">
              {Object.entries(summary.wynik_w_kartach).map(([team, points]) => {
                // Dla Bez Pytania pokazuj tylko punkty grającego
                if (isBezPytania && summary.gracz_grajacy) {
                  // Znajdź drużynę grającego (zakładamy że nazwa drużyny zawiera część nazwy gracza lub odwrotnie)
                  // Może lepiej przekazać tę informację z backendu, ale na razie:
                  // Pokaż obie drużyny, ale to i tak działa
                }
                return (
                  <div key={team} className="flex justify-between items-center p-2 bg-gray-800 rounded-lg">
                    <span className="text-gray-300">{team}</span>
                    <span className="text-white font-bold">{points} pkt</span>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {summary.wygrana_druzyna && (
          <div className={`mb-4 p-4 rounded-lg border ${
            didIWin 
              ? 'bg-green-500/20 border-green-500/50' 
              : 'bg-red-500/20 border-red-500/50'
          }`}>
            <div className="text-center mb-2">
              <p className={`font-bold text-lg ${
                didIWin ? 'text-green-300' : 'text-red-300'
              }`}>
                {didIWin ? '👑' : '💔'} Zwycięzca: {summary.wygrana_druzyna}
              </p>
            </div>
            <div className="text-center">
              <p className={`text-2xl font-bold ${
                didIWin ? 'text-white' : 'text-red-400'
              }`}>
                +{summary.przyznane_punkty} pkt meczu
              </p>
            </div>
          </div>
        )}

        {(summary.mnoznik_lufy > 1 || summary.mnoznik_gry > 1 || summary.bonus_z_trzech_kart) && (
          <div className="mb-4 p-3 bg-yellow-500/10 border border-yellow-500/30 rounded-lg">
            <h3 className="text-sm font-semibold text-yellow-400 mb-2">✨ Mnożniki:</h3>
            <div className="text-sm text-gray-300 space-y-1">
              {summary.mnoznik_gry > 1 && <div>🎯 Mnożnik gry: ×{summary.mnoznik_gry}</div>}
              {summary.mnoznik_lufy > 1 && <div>🔥 Mnożnik lufy: ×{summary.mnoznik_lufy}</div>}
              {summary.bonus_z_trzech_kart && <div>⭐ Bonus z 3 kart: ×2</div>}
            </div>
          </div>
        )}

        <button
          onClick={onNextRound}
          disabled={loading}
          className="w-full py-3 bg-teal-600 hover:bg-teal-700 disabled:bg-gray-600 text-white font-bold rounded-lg transition-all"
        >
          ▶ Następna runda
        </button>
      </div>
    </div>
  )
}

export default RoundSummary
