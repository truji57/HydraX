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
    case 'copy_ok':
      return `${data.slave || ''}: ${data.action} OK ${data.symbol} ${data.contracts || ''} (master_ticket ${data.master_ticket})`;
    case 'copy_error':
      return `${data.slave || ''}: ${data.action} ERROR ${data.symbol} - ${data.error || 'unknown'}`;
    case 'worker_error':
      return `ERROR: ${data.worker || ''} - ${data.error || 'sin conexion'}`;
    default:
      return '';
  }
}