export const formatters={date:t=>new Date(t*1000).toLocaleString('pl-PL'),time:s=>{const m=Math.floor(s/60);const sec=s%60;return `${m}:${sec.toString().padStart(2,'0')}`}};
