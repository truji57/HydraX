export function formatEvent(type: string, data: Record<string, unknown>): string {
  switch (type) {
    case 'position_open':
      return `${data.master || ''}: ${data.direction} ${data.contracts || data.volume}x ${data.symbol} (ticket ${data.ticket})`;
    case 'position_close':
      return `${data.master || ''}: cerrada ${data.symbol} (ticket ${data.ticket})`;
    case 'position_modify':
      return `${data.master || ''}: SL/TP modificado ${data.symbol} (ticket ${data.ticket})`;
    case 'order_pending':
      return `${data.master || ''}: orden pendiente ${data.type || ''} ${data.direction || ''} ${data.quantity || ''}x ${data.symbol || ''}`;
    case 'order_removed':
      return `${data.master || ''}: orden eliminada (ticket ${data.ticket})`;
    case 'copy_ok': {
      const vol = data.contracts ?? data.volume;
      const volTxt = vol !== undefined && vol !== null && vol !== '' ? ` ${vol}` : '';
      let sltp = '';
      if (typeof data.sl_usd === 'number' && data.sl_usd > 0) sltp += ` | SL -$${data.sl_usd.toFixed(2)}`;
      if (typeof data.tp_usd === 'number' && data.tp_usd > 0) sltp += ` | TP +$${data.tp_usd.toFixed(2)}`;
      return `${data.slave || ''}: ${data.action} OK ${data.symbol}${volTxt}${sltp} (master_ticket ${data.master_ticket})`;
    }
    case 'copy_error':
      return `${data.slave || ''}: ${data.action} ERROR ${data.symbol} - ${data.error || 'unknown'}`;
    case 'worker_error':
      return `ERROR: ${data.worker || ''} - ${data.error || 'sin conexion'}`;
    default:
      return '';
  }
}