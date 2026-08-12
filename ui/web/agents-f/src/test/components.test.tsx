import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { Text } from '../components/catalogue/Text';
import { Input } from '../components/catalogue/Input';
import { Checkbox } from '../components/catalogue/Checkbox';
import { Dropdown } from '../components/catalogue/Dropdown';
import { Range } from '../components/catalogue/Range';
import { A2uiRenderer } from '../components/catalogue/A2uiRenderer';

describe('Firecrawl Light A2UI Component Catalogue', () => {

  describe('Text component', () => {
    it('renders text with default body variant', () => {
      render(<Text text="Hello Firecrawl" />);
      const el = screen.getByText('Hello Firecrawl');
      expect(el).toBeInTheDocument();
      expect(el.tagName).toBe('P');
    });

    it('renders heading variant as H1', () => {
      render(<Text text="Headline Display" variant="headline-display" />);
      const el = screen.getByText('Headline Display');
      expect(el.tagName).toBe('H1');
      expect(el).toHaveClass('typography-headline-display');
    });
  });

  describe('Input component', () => {
    it('renders input with label and placeholder', () => {
      render(<Input id="test-input" label="Username" placeholder="Enter username..." value="john" />);
      expect(screen.getByLabelText('Username')).toBeInTheDocument();
      expect(screen.getByPlaceholderText('Enter username...')).toHaveValue('john');
    });

    it('calls onChange when user types', () => {
      const handleChange = vi.fn();
      render(<Input id="test-input" label="Search" onChange={handleChange} />);
      const input = screen.getByLabelText('Search');
      fireEvent.change(input, { target: { value: 'Firecrawl API' } });
      expect(handleChange).toHaveBeenCalledWith('Firecrawl API');
    });
  });

  describe('Checkbox component', () => {
    it('renders checkbox and toggles state on click', () => {
      const handleChange = vi.fn();
      render(<Checkbox id="chk-test" label="Accept Terms" checked={false} onChange={handleChange} />);
      const checkbox = screen.getByLabelText('Accept Terms');
      expect(checkbox).not.toBeChecked();
      fireEvent.click(checkbox);
      expect(handleChange).toHaveBeenCalledWith(true);
    });
  });

  describe('Dropdown component', () => {
    it('renders select options and updates value', () => {
      const handleChange = vi.fn();
      const options = [
        { label: 'Option A', value: 'opt-a' },
        { label: 'Option B', value: 'opt-b' },
      ];
      render(<Dropdown id="drop-test" label="Choice" value="opt-a" options={options} onChange={handleChange} />);
      const select = screen.getByLabelText('Choice');
      expect(select).toHaveValue('opt-a');
      fireEvent.change(select, { target: { value: 'opt-b' } });
      expect(handleChange).toHaveBeenCalledWith('opt-b');
    });
  });

  describe('Range component', () => {
    it('renders range slider with correct value badge', () => {
      const handleChange = vi.fn();
      render(<Range id="range-test" label="Limit" value={42} min={0} max={100} onChange={handleChange} />);
      expect(screen.getByText('42')).toBeInTheDocument();
      const slider = screen.getByLabelText('Limit');
      fireEvent.change(slider, { target: { value: '80' } });
      expect(handleChange).toHaveBeenCalledWith(80);
    });
  });

  describe('A2uiRenderer', () => {
    it('renders flat A2UI components bound to data model', () => {
      const handleDataChange = vi.fn();
      const surface = {
        surfaceId: 'test-surf',
        dataModel: { query: 'Firecrawl' },
        components: [
          {
            id: 'inp-1',
            component: 'Input' as const,
            label: 'Search Query',
            value: { path: '/query' },
          },
        ],
      };
      render(<A2uiRenderer surface={surface} onDataModelChange={handleDataChange} />);
      const input = screen.getByLabelText('Search Query');
      expect(input).toHaveValue('Firecrawl');
      fireEvent.change(input, { target: { value: 'New Query' } });
      expect(handleDataChange).toHaveBeenCalledWith('query', 'New Query');
    });
  });

});
