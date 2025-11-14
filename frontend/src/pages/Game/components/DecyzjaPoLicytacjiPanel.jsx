function DecyzjaPoLicytacjiPanel({ onAction, loading }) {
  const handleZmianaKontraktu = (kontrakt) => {
    onAction({ typ: 'zmiana_kontraktu', kontrakt })
  }

  const handleGrajNormalnie = () => {
    onAction({ typ: 'graj_normalnie' })
  }

  return (
    <div className="bg-gray-900/95 backdrop-blur-sm rounded-xl p-6 border-2 border-teal-600/50 shadow-2xl max-w-md">
      <h3 className="text-white font-bold text-xl mb-4 text-center">🎲 Twoja decyzja</h3>
      
      <p className="text-gray-300 text-sm mb-6 text-center">
        Przeciwnicy spasowali. Co chcesz zrobić?
      </p>

      {/* PRZYCISKI AKCJI */}
      <div className="space-y-3">
        {/* Gorsza z 3 */}
        <button
          onClick={() => handleZmianaKontraktu('GORSZA')}
          disabled={loading}
          className="
            w-full py-4 bg-orange-600 hover:bg-orange-700 disabled:bg-gray-600
            text-white font-bold text-lg rounded-lg transition-all transform hover:scale-105
            disabled:opacity-50 disabled:cursor-not-allowed
          "
        >
          🎯 Gorsza z 3
        </button>

        {/* Lepsza z 3 */}
        <button
          onClick={() => handleZmianaKontraktu('LEPSZA')}
          disabled={loading}
          className="
            w-full py-4 bg-green-600 hover:bg-green-700 disabled:bg-gray-600
            text-white font-bold text-lg rounded-lg transition-all transform hover:scale-105
            disabled:opacity-50 disabled:cursor-not-allowed
          "
        >
          ⭐ Lepsza z 3
        </button>

        {/* Graj Normalnie */}
        <button
          onClick={handleGrajNormalnie}
          disabled={loading}
          className="
            w-full py-4 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600
            text-white font-bold text-lg rounded-lg transition-all transform hover:scale-105
            disabled:opacity-50 disabled:cursor-not-allowed
          "
        >
          ▶️ Graj normalnie
        </button>
      </div>
    </div>
  )
}

export default DecyzjaPoLicytacjiPanel
