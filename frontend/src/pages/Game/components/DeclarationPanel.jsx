import { useState } from 'react'

function DeclarationPanel({ onDeclare, loading }) {
  const [selectedContract, setSelectedContract] = useState(null)
  const [selectedTrump, setSelectedTrump] = useState(null)

  const suits = [
    { name: 'Czerwien', symbol: '♥' },
    { name: 'Dzwonek', symbol: '♦' },
    { name: 'Zoladz', symbol: '♣' },
    { name: 'Wino', symbol: '♠' }
  ]

  const contracts = [
    { id: 'NORMALNA', label: 'Normalna', needsTrump: true, color: 'bg-blue-600 hover:bg-blue-700' },
    { id: 'BEZ_PYTANIA', label: 'Nie pytam z 3', needsTrump: true, color: 'bg-purple-600 hover:bg-purple-700' },
    { id: 'GORSZA', label: 'Gorsza z 3', needsTrump: false, color: 'bg-orange-600 hover:bg-orange-700' },
    { id: 'LEPSZA', label: 'Lepsza z 3', needsTrump: false, color: 'bg-green-600 hover:bg-green-700' }
  ]

  const handleConfirm = () => {
    if (!selectedContract) return
    const contract = contracts.find(c => c.id === selectedContract)
    if (contract.needsTrump && !selectedTrump) return
    
    onDeclare(selectedContract, selectedTrump)
  }

  const canConfirm = selectedContract && (!contracts.find(c => c.id === selectedContract)?.needsTrump || selectedTrump)

  return (
    <div className="bg-gray-900/95 backdrop-blur-sm rounded-xl p-6 border-2 border-gray-700 shadow-2xl max-w-md">
      <h3 className="text-white font-bold text-xl mb-4 text-center">Wybierz kontrakt</h3>
      
      {/* PRZYCISKI KONTRAKTÓW */}
      <div className="grid grid-cols-2 gap-3 mb-4">
        {contracts.map(contract => (
          <button
            key={contract.id}
            onClick={() => {
              setSelectedContract(contract.id)
              if (!contract.needsTrump) setSelectedTrump(null)
            }}
            disabled={loading}
            className={`
              ${contract.color}
              ${selectedContract === contract.id ? 'ring-4 ring-yellow-400' : ''}
              px-4 py-3 text-white font-bold rounded-lg transition-all transform hover:scale-105
              disabled:opacity-50 disabled:cursor-not-allowed
            `}
          >
            {contract.label}
          </button>
        ))}
      </div>

      {/* WYBÓR ATUTU */}
      {selectedContract && contracts.find(c => c.id === selectedContract)?.needsTrump && (
        <div className="mb-4">
          <p className="text-gray-300 text-sm mb-2 text-center">Wybierz atut:</p>
          <div className="grid grid-cols-4 gap-2">
            {suits.map(suit => (
              <button
                key={suit.name}
                onClick={() => setSelectedTrump(suit.name)}
                disabled={loading}
                className={`
                  ${selectedTrump === suit.name ? 'bg-yellow-500/30 ring-2 ring-yellow-400' : 'bg-gray-800'}
                  p-3 rounded-lg transition-all transform hover:scale-110
                  disabled:opacity-50 disabled:cursor-not-allowed
                `}
              >
                <div className="text-3xl">{suit.symbol}</div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* PRZYCISK POTWIERDZENIA */}
      <button
        onClick={handleConfirm}
        disabled={!canConfirm || loading}
        className="
          w-full py-3 bg-teal-600 hover:bg-teal-700 disabled:bg-gray-600 
          text-white font-bold rounded-lg transition-all transform hover:scale-105
          disabled:opacity-50 disabled:cursor-not-allowed
        "
      >
        {loading ? 'Wysyłam...' : 'Potwierdź deklarację'}
      </button>
    </div>
  )
}

export default DeclarationPanel
