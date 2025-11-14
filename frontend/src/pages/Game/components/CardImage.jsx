function CardImage({ card, size = 'md', onClick, disabled, playable, highlight = false, selected = false }) {
  const sizes = {
    sm: 'w-10 h-16',
    md: 'w-14 h-22',
    lg: 'w-16 h-24'
  }
  
  const cardPath = card.replace(' ', '')
  const imagePath = `/karty/${cardPath}.png`
  
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`
        ${sizes[size]} rounded-lg shadow-xl transition-all relative
        ${
          selected
            ? 'scale-110 -translate-y-4 shadow-teal-500/50'
            : highlight
            ? 'ring-4 ring-yellow-400 shadow-yellow-500/50 animate-pulse'
            : !disabled && playable
            ? 'hover:scale-110 hover:-translate-y-3 hover:shadow-2xl cursor-pointer border-2 border-transparent hover:border-teal-500' 
            : disabled
            ? 'opacity-50 cursor-not-allowed' 
            : 'cursor-pointer'
        }
      `}
    >
      {highlight && (
        <div className="absolute -top-2 -right-2 bg-yellow-500 text-xs font-bold px-2 py-0.5 rounded-full z-10 shadow-lg">
          ✨
        </div>
      )}
      {selected && (
        <div className="absolute -top-2 -right-2 bg-teal-500 text-xs font-bold px-2 py-0.5 rounded-full z-10 shadow-lg">
          ✔️
        </div>
      )}
      <img 
        src={imagePath} 
        alt={card} 
        className="w-full h-full object-cover rounded-lg"
        onError={(e) => {
          console.error('Błąd ładowania karty:', card)
          e.target.style.display = 'none'
        }}
      />
    </button>
  )
}

export default CardImage
