import React from 'react';
import { Text } from './Text';
import { Input } from './Input';
import { Checkbox } from './Checkbox';
import { Dropdown } from './Dropdown';
import { Range } from './Range';

export interface A2uiComponentDef {
  id: string;
  component: 'Text' | 'Input' | 'TextField' | 'Checkbox' | 'CheckBox' | 'Dropdown' | 'ChoicePicker' | 'Range' | 'Slider' | 'Column' | 'Row' | 'Card';
  text?: string | { path: string };
  label?: string;
  value?: any | { path: string };
  placeholder?: string;
  variant?: any;
  options?: Array<{ label: string; value: string }>;
  min?: number;
  max?: number;
  step?: number;
  disabled?: boolean;
  children?: string[];
  action?: { event: { name: string; context?: Record<string, any> } };
}

export interface A2uiSurfaceState {
  surfaceId: string;
  components: A2uiComponentDef[];
  dataModel: Record<string, any>;
}

export interface A2uiRendererProps {
  surface: A2uiSurfaceState;
  onDataModelChange?: (path: string, value: any) => void;
  onAction?: (actionName: string, componentId: string, context?: Record<string, any>) => void;
}

// Helper to resolve JSON Pointer path or raw value
const resolvePathValue = (val: any, dataModel: Record<string, any>): any => {
  if (val && typeof val === 'object' && 'path' in val) {
    const cleanPath = val.path.replace(/^\//, '');
    return dataModel[cleanPath] !== undefined ? dataModel[cleanPath] : '';
  }
  return val;
};

export const A2uiRenderer: React.FC<A2uiRendererProps> = ({
  surface,
  onDataModelChange,
  onAction,
}) => {
  const { components, dataModel } = surface;

  // Map of component by ID
  const componentMap = React.useMemo(() => {
    const map = new Map<string, A2uiComponentDef>();
    components.forEach((c) => map.set(c.id, c));
    return map;
  }, [components]);

  const renderComponentNode = (id: string): React.ReactNode => {
    const comp = componentMap.get(id);
    if (!comp) return null;

    switch (comp.component) {
      case 'Text': {
        const textVal = resolvePathValue(comp.text, dataModel) ?? '';
        return (
          <Text
            key={comp.id}
            id={comp.id}
            text={String(textVal)}
            variant={comp.variant || 'body-md'}
          />
        );
      }

      case 'Input':
      case 'TextField': {
        const rawPath = typeof comp.value === 'object' && 'path' in comp.value ? comp.value.path : comp.id;
        const val = resolvePathValue(comp.value, dataModel) ?? '';
        return (
          <Input
            key={comp.id}
            id={comp.id}
            label={comp.label}
            placeholder={comp.placeholder}
            value={String(val)}
            disabled={comp.disabled}
            onChange={(newVal) => {
              const cleanPath = typeof rawPath === 'string' ? rawPath.replace(/^\//, '') : comp.id;
              onDataModelChange?.(cleanPath, newVal);
              if (comp.action) {
                onAction?.(comp.action.event.name, comp.id, { value: newVal });
              }
            }}
          />
        );
      }

      case 'Checkbox':
      case 'CheckBox': {
        const rawPath = typeof comp.value === 'object' && 'path' in comp.value ? comp.value.path : comp.id;
        const val = Boolean(resolvePathValue(comp.value, dataModel));
        return (
          <Checkbox
            key={comp.id}
            id={comp.id}
            label={comp.label}
            checked={val}
            disabled={comp.disabled}
            onChange={(newChecked) => {
              const cleanPath = typeof rawPath === 'string' ? rawPath.replace(/^\//, '') : comp.id;
              onDataModelChange?.(cleanPath, newChecked);
              if (comp.action) {
                onAction?.(comp.action.event.name, comp.id, { checked: newChecked });
              }
            }}
          />
        );
      }

      case 'Dropdown':
      case 'ChoicePicker': {
        const rawPath = typeof comp.value === 'object' && 'path' in comp.value ? comp.value.path : comp.id;
        const val = resolvePathValue(comp.value, dataModel) ?? '';
        return (
          <Dropdown
            key={comp.id}
            id={comp.id}
            label={comp.label}
            placeholder={comp.placeholder}
            value={String(val)}
            options={comp.options || []}
            disabled={comp.disabled}
            onChange={(newVal) => {
              const cleanPath = typeof rawPath === 'string' ? rawPath.replace(/^\//, '') : comp.id;
              onDataModelChange?.(cleanPath, newVal);
              if (comp.action) {
                onAction?.(comp.action.event.name, comp.id, { value: newVal });
              }
            }}
          />
        );
      }

      case 'Range':
      case 'Slider': {
        const rawPath = typeof comp.value === 'object' && 'path' in comp.value ? comp.value.path : comp.id;
        const val = Number(resolvePathValue(comp.value, dataModel) ?? comp.min ?? 0);
        return (
          <Range
            key={comp.id}
            id={comp.id}
            label={comp.label}
            value={val}
            min={comp.min}
            max={comp.max}
            step={comp.step}
            disabled={comp.disabled}
            onChange={(newNum) => {
              const cleanPath = typeof rawPath === 'string' ? rawPath.replace(/^\//, '') : comp.id;
              onDataModelChange?.(cleanPath, newNum);
              if (comp.action) {
                onAction?.(comp.action.event.name, comp.id, { value: newNum });
              }
            }}
          />
        );
      }

      case 'Column': {
        return (
          <div key={comp.id} className="flex flex-col gap-4 w-full">
            {(comp.children || []).map(renderComponentNode)}
          </div>
        );
      }

      case 'Row': {
        return (
          <div key={comp.id} className="flex flex-row items-center gap-4 w-full flex-wrap">
            {(comp.children || []).map(renderComponentNode)}
          </div>
        );
      }

      case 'Card': {
        return (
          <div key={comp.id} className="firecrawl-card flex flex-col gap-4 w-full">
            {(comp.children || []).map(renderComponentNode)}
          </div>
        );
      }

      default:
        return null;
    }
  };

  // Find root or top-level components
  const childIds = new Set(components.flatMap((c) => c.children || []));
  const rootComponents = components.filter((c) => !childIds.has(c.id));

  return (
    <div className="flex flex-col gap-4 w-full">
      {rootComponents.map((c) => renderComponentNode(c.id))}
    </div>
  );
};

export default A2uiRenderer;
