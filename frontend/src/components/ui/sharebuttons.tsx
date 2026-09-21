import { useRef } from 'react';
import { Button } from './button';
import { readJsonFile } from '../../lib/share';
import { Upload, Download } from 'lucide-react';

export function ExportButton({ label, onClick, disabled, size }: {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  size?: 'sm' | 'md' | 'lg';
}) {
  return (
    <Button variant="outline" size={size || 'sm'} onClick={onClick} disabled={disabled}>
      <Download size={14} /> {label}
    </Button>
  );
}

export function ImportButton({ label, onImport, disabled, size }: {
  label: string;
  onImport: (data: Record<string, unknown>) => Promise<void> | void;
  disabled?: boolean;
  size?: 'sm' | 'md' | 'lg';
}) {
  const ref = useRef<HTMLInputElement>(null);
  return (
    <>
      <input
        ref={ref}
        type="file"
        accept=".json,application/json"
        className="hidden"
        onChange={async (e) => {
          const f = e.target.files?.[0];
          if (f) {
            try {
              await onImport(await readJsonFile(f));
            } catch {
              // el manejo del toast lo hace la pagina
            }
          }
          e.target.value = '';
        }}
      />
      <Button variant="outline" size={size || 'sm'} onClick={() => ref.current?.click()} disabled={disabled}>
        <Upload size={14} /> {label}
      </Button>
    </>
  );
}