function PlayerCard({ player, isActive, cardCount }) {
  return (
    <div className="flex flex-col items-center gap-2">
      {/* Awatar */}
      <div className={`
        ${isActive ? 'bg-yellow-500/20 border-yellow-500 shadow-lg shadow-yellow-500/20' : 'bg-gray-800/70 border-gray-700'}
        border-2 rounded-xl p-2 backdrop-blur-sm transition-all flex items-center gap-2
      `}>
        <div className="text-xl">
          {player.is_bot ? '🤖' : '👤'}
        </div>
        <p className="text-white font-bold text-sm">{player.name}</p>
      </div>
      
      {/* Karty (rewers) */}
      <div className="flex gap-1">
        {Array.from({ length: Math.min(cardCount, 6) }).map((_, idx) => (
          <img 
            key={idx}
            src="/karty/rewers.png" 
            alt="Karta" 
            className="w-18 h-28 rounded-lg shadow-xl"
          />
        ))}
      </div>
    </div>
  )
}

export default PlayerCard
