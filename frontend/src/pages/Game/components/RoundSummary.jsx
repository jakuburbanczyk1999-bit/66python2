function RoundSummary({ summary, onNextRound, loading, myTeam, myName, playerCount = 4, hasVoted, votes }) {
  const is3Player = playerCount === 3;
  
  // Dla 3p backend zwraca 'wygrani_gracze' (lista), dla 4p 'wygrana_druzyna' (string)
  const winnerDisplay = is3Player 
    ? (summary.wygrani_gracze && summary.wygrani_gracze.length > 0 ? summary.wygrani_gracze.join(', ') : null)
    : summary.wygrana_druzyna;
  
  // Sprawdź czy ja wygrałem
  const didIWin = is3Player 
    ? (summary.wygrani_gracze && summary.wygrani_gracze.includes(myName))
    : summary.wygrana_druzyna === myTeam;
  
  const isSoloContract = summary.kontrakt === 'LEPSZA' || summary.kontrakt === 'GORSZA';
  const shouldShowCardPoints = !isSoloContract;
  
  return (
    <div className="fixed inset-0 flex items-center justify-center bg-black/70 backdrop-blur-sm z-[100]">
      <div className="bg-gray-900 rounded-xl p-8 max-w-lg border border-gray-700 shadow-2xl">
        <h2 className="text-2xl font-bold text-white mb-4 text-center">
          Rozdanie zakonczone
        </h2>
        
        {summary.powod && (
          <div className="mb-4 p-3 bg-blue-500/10 border border-blue-500/30 rounded-lg text-center">
            <p className="text-blue-300 text-sm">{summary.powod}</p>
          </div>
        )}

        {shouldShowCardPoints && summary.wynik_w_kartach && (
          <div className="mb-4">
            <h3 className="text-sm font-semibold text-gray-400 mb-2">Punkty w kartach:</h3>
            <div className="space-y-2">
              {Object.entries(summary.wynik_w_kartach).map(([entity, points]) => {
                const isMe = is3Player ? entity === myName : entity === myTeam;
                return (
                  <div key={entity} className={`flex justify-between items-center p-2 rounded-lg ${
                    isMe ? 'bg-teal-800/50' : 'bg-gray-800'
                  }`}>
                    <span className={isMe ? 'text-teal-300' : 'text-gray-300'}>{entity}</span>
                    <span className="text-white font-bold">{points} pkt</span>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {winnerDisplay && (
          <div className={`mb-4 p-4 rounded-lg border ${
            didIWin 
              ? 'bg-green-500/20 border-green-500/50' 
              : 'bg-red-500/20 border-red-500/50'
          }`}>
            <div className="text-center mb-2">
              <p className={`font-bold text-lg ${
                didIWin ? 'text-green-300' : 'text-red-300'
              }`}>
                {is3Player ? 'Zwyciezca: ' : 'Zwyciezcy: '}{winnerDisplay}
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

        {is3Player && summary.punkty_meczowe && (
          <div className="mb-4 p-3 bg-gray-800/50 rounded-lg">
            <h3 className="text-sm font-semibold text-gray-400 mb-2">Punkty w meczu:</h3>
            <div className="space-y-1">
              {Object.entries(summary.punkty_meczowe).map(([name, points]) => (
                <div key={name} className="flex justify-between items-center">
                  <span className={name === myName ? 'text-teal-400' : 'text-gray-300'}>{name}</span>
                  <span className="text-yellow-400 font-bold">{points}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {(summary.mnoznik_lufy > 1 || summary.mnoznik_gry > 1 || summary.bonus_z_trzech_kart) && (
          <div className="mb-4 p-3 bg-yellow-500/10 border border-yellow-500/30 rounded-lg">
            <h3 className="text-sm font-semibold text-yellow-400 mb-2">Mnozniki:</h3>
            <div className="text-sm text-gray-300 space-y-1">
              {summary.mnoznik_gry > 1 && <div>Mnoznik gry: x{summary.mnoznik_gry}</div>}
              {summary.mnoznik_lufy > 1 && <div>Mnoznik lufy: x{summary.mnoznik_lufy}</div>}
              {summary.bonus_z_trzech_kart && <div>Bonus z 3 kart: x2</div>}
            </div>
          </div>
        )}

        {votes && votes.votes && votes.votes.length > 0 && (
          <div className="mb-4 p-3 bg-gray-800/50 rounded-lg">
            <p className="text-xs text-gray-400 mb-2 text-center">Czekam na graczy...</p>
            <div className="flex flex-wrap gap-1 justify-center">
              {votes.votes.map((voter, idx) => (
                <span key={idx} className="px-2 py-0.5 bg-green-500/20 text-green-400 text-xs rounded-full">
                  {voter}
                </span>
              ))}
            </div>
            <p className="text-xs text-gray-500 mt-2 text-center">
              {votes.votes.length} / {votes.totalPlayers} graczy
            </p>
          </div>
        )}

        <button
          onClick={onNextRound}
          disabled={loading || hasVoted}
          className={`w-full py-3 font-bold rounded-lg transition-all ${
            hasVoted 
              ? 'bg-green-600 text-white cursor-default' 
              : 'bg-teal-600 hover:bg-teal-700 disabled:bg-gray-600 text-white'
          }`}
        >
          {loading ? '...' : hasVoted ? 'Czekam na innych graczy' : 'Nastepna runda'}
        </button>
      </div>
    </div>
  )
}

export default RoundSummary
