function PytaniePanel({ onAction, loading }) {
  const handlePytanie = () => {
    onAction({ typ: 'pytanie' })
  }

  const handleNiePytam = () => {
    onAction({ typ: 'nie_pytam' })
  }

  return (
    <div className="bg-gray-900/95 backdrop-blur-sm rounded-xl p-6 border-2 border-blue-600/50 shadow-2xl max-w-md">
      <h3 className="text-white font-bold text-xl mb-4 text-center">Pytanie</h3>
      
      <p className="text-gray-300 text-sm mb-6 text-center">
        Czy chcesz zapytać o przebicie?
      </p>

      {/* PRZYCISKI AKCJI */}
      <div className="space-y-3">
        {/* Pytam */}
        <button
          onClick={handlePytanie}
          disabled={loading}
          className="
            w-full py-4 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600
            text-white font-bold text-lg rounded-lg transition-all transform hover:scale-105
            disabled:opacity-50 disabled:cursor-not-allowed
          "
        >
          Pytam
        </button>

        {/* Nie pytam (zmiana na Bez Pytania) */}
        <button
          onClick={handleNiePytam}
          disabled={loading}
          className="
            w-full py-4 bg-purple-600 hover:bg-purple-700 disabled:bg-gray-600
            text-white font-bold text-lg rounded-lg transition-all transform hover:scale-105
            disabled:opacity-50 disabled:cursor-not-allowed
          "
        >
          Nie pytam
        </button>
      </div>
    </div>
  )
}

export default PytaniePanel
