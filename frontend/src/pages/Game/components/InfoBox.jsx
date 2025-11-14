function InfoBox({ label, value, color }) {
  const colors = {
    blue: 'bg-blue-500/10 border-blue-500/30',
    purple: 'bg-purple-500/10 border-purple-500/30',
    yellow: 'bg-yellow-500/10 border-yellow-500/30',
    green: 'bg-green-500/10 border-green-500/30'
  }
  
  return (
    <div className={`p-1.5 rounded-lg ${colors[color]} border`}>
      <div className="text-xs text-gray-400">{label}</div>
      <div className="text-sm font-bold text-white">{value}</div>
    </div>
  )
}

export default InfoBox
