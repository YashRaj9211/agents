import { useState } from 'react';
import {
  Text,
  Input,
  Checkbox,
  Dropdown,
  Range,
  A2uiRenderer,
  type A2uiSurfaceState,
} from './components/catalogue';

export function App() {
  const [activeTab, setActiveTab] = useState<'catalogue' | 'sandbox'>('catalogue');

  // Catalogue state
  const [inputText, setInputText] = useState('Firecrawl Web Data API');
  const [isCheckxChecked, setIsCheckxChecked] = useState(true);
  const [selectedFormat, setSelectedFormat] = useState('json');
  const [rangeVal, setRangeVal] = useState(75);

  // Sandbox state
  const [surfaceState, setSurfaceState] = useState<A2uiSurfaceState>({
    surfaceId: 'firecrawl-demo-surface',
    dataModel: {
      userQuery: 'https://firecrawl.dev',
      enableSubdomains: true,
      outputFormat: 'markdown',
      crawlLimit: 50,
    },
    components: [
      {
        id: 'root-card',
        component: 'Card',
        children: ['title', 'subtitle', 'url-input', 'subdomain-check', 'format-select', 'limit-range'],
      },
      {
        id: 'title',
        component: 'Text',
        text: 'Firecrawl API Configuration',
        variant: 'headline-md',
      },
      {
        id: 'subtitle',
        component: 'Text',
        text: 'Configure real-time web scraping parameters generated via A2UI protocol v0.9',
        variant: 'body-sm',
      },
      {
        id: 'url-input',
        component: 'Input',
        label: 'Target URL',
        value: { path: '/userQuery' },
        placeholder: 'https://example.com',
      },
      {
        id: 'subdomain-check',
        component: 'Checkbox',
        label: 'Include all subdomains during crawl',
        value: { path: '/enableSubdomains' },
      },
      {
        id: 'format-select',
        component: 'Dropdown',
        label: 'Output Format',
        value: { path: '/outputFormat' },
        options: [
          { label: 'Markdown (.md)', value: 'markdown' },
          { label: 'JSON Structure (.json)', value: 'json' },
          { label: 'Raw HTML (.html)', value: 'html' },
        ],
      },
      {
        id: 'limit-range',
        component: 'Range',
        label: 'Max Pages to Crawl',
        value: { path: '/crawlLimit' },
        min: 1,
        max: 200,
        step: 5,
      },
    ],
  });

  const [jsonInput, setJsonInput] = useState(
    JSON.stringify(surfaceState, null, 2)
  );
  const [jsonError, setJsonError] = useState<string | null>(null);

  // Action log
  const [actionLogs, setActionLogs] = useState<
    Array<{ timestamp: string; action: string; componentId: string; context?: any }>
  >([]);

  const handleJsonUpdate = (rawJson: string) => {
    setJsonInput(rawJson);
    try {
      const parsed = JSON.parse(rawJson);
      if (parsed.surfaceId && Array.isArray(parsed.components) && parsed.dataModel) {
        setSurfaceState(parsed);
        setJsonError(null);
      } else {
        setJsonError('JSON must contain surfaceId, components array, and dataModel object.');
      }
    } catch (err: any) {
      setJsonError(err.message);
    }
  };

  const logAction = (actionName: string, componentId: string, context?: any) => {
    const newLog = {
      timestamp: new Date().toLocaleTimeString(),
      action: actionName,
      componentId,
      context,
    };
    setActionLogs((prev) => [newLog, ...prev.slice(0, 19)]);
  };

  const updateSandboxDataModel = (path: string, val: any) => {
    setSurfaceState((prev) => {
      const nextDataModel = { ...prev.dataModel, [path]: val };
      const nextState = { ...prev, dataModel: nextDataModel };
      setJsonInput(JSON.stringify(nextState, null, 2));
      return nextState;
    });
  };

  return (
    <div className="min-h-screen bg-[#F9F9F9] text-[#262626] flex flex-col font-sans">
      {/* Navigation Header */}
      <header className="bg-[#FFFFFF] border-b border-[#E5E7EB] sticky top-0 z-20 px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-[#FA5D19] flex items-center justify-center text-white font-bold text-lg shadow-sm">
              F
            </div>
            <div>
              <span className="typography-headline-sm font-semibold tracking-tight">
                Firecrawl
              </span>
              <span className="typography-micro uppercase text-[#6B7280] ml-2 tracking-widest bg-[#F9F9F9] px-2 py-0.5 rounded-full border border-[#E5E7EB]">
                A2UI Light v0.9
              </span>
            </div>
          </div>

          <div className="flex items-center bg-[#F9F9F9] p-1 rounded-xl border border-[#E5E7EB]">
            <button
              onClick={() => setActiveTab('catalogue')}
              className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-all ${
                activeTab === 'catalogue'
                  ? 'bg-[#FFFFFF] text-[#262626] shadow-sm'
                  : 'text-[#6B7280] hover:text-[#262626]'
              }`}
            >
              Component Catalogue
            </button>
            <button
              onClick={() => setActiveTab('sandbox')}
              className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-all ${
                activeTab === 'sandbox'
                  ? 'bg-[#FFFFFF] text-[#262626] shadow-sm'
                  : 'text-[#6B7280] hover:text-[#262626]'
              }`}
            >
              A2UI Protocol Sandbox
            </button>
          </div>
        </div>
      </header>

      {/* Main Content Container */}
      <main className="max-w-7xl mx-auto w-full px-6 py-8 flex-1">
        {activeTab === 'catalogue' ? (
          <div className="flex flex-col gap-8">
            {/* Hero Header */}
            <div className="flex flex-col gap-2 max-w-2xl">
              <span className="firecrawl-chip text-[#FA5D19] border-[#FA5D19]/20 self-start">
                Design Token & Primitives
              </span>
              <h1 className="typography-headline-display">
                A2UI Component Catalogue
              </h1>
              <p className="typography-body-lg text-[#6B7280]">
                A clean, high-contrast SaaS component system for modern agent web apps, styled with vivid orange emphasis and Swiss typography.
              </p>
            </div>

            {/* Grid Showcase of the 5 requested primitives */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* 1. Text Component */}
              <div className="firecrawl-card flex flex-col gap-4">
                <div className="flex items-center justify-between border-b border-[#E5E7EB] pb-3">
                  <h3 className="typography-headline-sm">1. Text (`Text`)</h3>
                  <span className="typography-micro uppercase tracking-wider text-[#6B7280] bg-[#F9F9F9] px-2 py-0.5 rounded border border-[#E5E7EB]">
                    Primitive
                  </span>
                </div>
                <p className="typography-body-sm text-[#6B7280]">
                  Renders styled headers and body text using Suisse font hierarchy.
                </p>
                <div className="space-y-3 bg-[#F9F9F9] p-4 rounded-lg border border-[#E5E7EB]">
                  <Text text="Display Headline (44px)" variant="headline-display" />
                  <Text text="Large Headline (36px)" variant="headline-lg" />
                  <Text text="Medium Headline (20px)" variant="headline-md" />
                  <Text text="Standard Body Text (16px) with clean reading line height." variant="body-md" />
                  <Text text="Small Label (12px)" variant="label-sm" />
                  <Text text="MICRO METADATA TEXT" variant="micro" />
                </div>
              </div>

              {/* 2. Input Component */}
              <div className="firecrawl-card flex flex-col gap-4">
                <div className="flex items-center justify-between border-b border-[#E5E7EB] pb-3">
                  <h3 className="typography-headline-sm">2. Input (`Input` / `TextField`)</h3>
                  <span className="typography-micro uppercase tracking-wider text-[#6B7280] bg-[#F9F9F9] px-2 py-0.5 rounded border border-[#E5E7EB]">
                    Primitive
                  </span>
                </div>
                <p className="typography-body-sm text-[#6B7280]">
                  Elevated input field with 16px radius (`rounded-xl`) and orange focus ring.
                </p>
                <div className="flex flex-col gap-4 bg-[#F9F9F9] p-4 rounded-lg border border-[#E5E7EB]">
                  <Input
                    label="API Key or Target Query"
                    value={inputText}
                    placeholder="Enter URL or API string..."
                    onChange={setInputText}
                  />
                  <div className="p-3 bg-[#FFFFFF] rounded-xl border border-[#E5E7EB] text-sm">
                    <span className="text-[#6B7280]">Live Bound State: </span>
                    <span className="font-mono text-[#FA5D19] font-medium">{inputText}</span>
                  </div>
                </div>
              </div>

              {/* 3. Checkbox Component */}
              <div className="firecrawl-card flex flex-col gap-4">
                <div className="flex items-center justify-between border-b border-[#E5E7EB] pb-3">
                  <h3 className="typography-headline-sm">3. Checkbox (`Checkbox` / `CheckBox`)</h3>
                  <span className="typography-micro uppercase tracking-wider text-[#6B7280] bg-[#F9F9F9] px-2 py-0.5 rounded border border-[#E5E7EB]">
                    Primitive
                  </span>
                </div>
                <p className="typography-body-sm text-[#6B7280]">
                  Custom tick control with Firecrawl orange fill state and crisp borders.
                </p>
                <div className="flex flex-col gap-4 bg-[#F9F9F9] p-4 rounded-lg border border-[#E5E7EB]">
                  <Checkbox
                    id="chk-demo"
                    label="Enable Deep Web Scraping & JavaScript Execution"
                    checked={isCheckxChecked}
                    onChange={setIsCheckxChecked}
                  />
                  <div className="p-3 bg-[#FFFFFF] rounded-xl border border-[#E5E7EB] text-sm">
                    <span className="text-[#6B7280]">Checked Status: </span>
                    <span className="font-mono text-[#FA5D19] font-medium">
                      {isCheckxChecked ? 'true' : 'false'}
                    </span>
                  </div>
                </div>
              </div>

              {/* 4. Dropdown Component */}
              <div className="firecrawl-card flex flex-col gap-4">
                <div className="flex items-center justify-between border-b border-[#E5E7EB] pb-3">
                  <h3 className="typography-headline-sm">4. Dropdown (`Dropdown` / `ChoicePicker`)</h3>
                  <span className="typography-micro uppercase tracking-wider text-[#6B7280] bg-[#F9F9F9] px-2 py-0.5 rounded border border-[#E5E7EB]">
                    Primitive
                  </span>
                </div>
                <p className="typography-body-sm text-[#6B7280]">
                  Select menu with custom chevron and subtle hover states.
                </p>
                <div className="flex flex-col gap-4 bg-[#F9F9F9] p-4 rounded-lg border border-[#E5E7EB]">
                  <Dropdown
                    id="dropdown-demo"
                    label="Response Format"
                    value={selectedFormat}
                    options={[
                      { label: 'JSON Object (.json)', value: 'json' },
                      { label: 'Clean Markdown (.md)', value: 'markdown' },
                      { label: 'Plain Text (.txt)', value: 'text' },
                    ]}
                    onChange={setSelectedFormat}
                  />
                  <div className="p-3 bg-[#FFFFFF] rounded-xl border border-[#E5E7EB] text-sm">
                    <span className="text-[#6B7280]">Selected Option: </span>
                    <span className="font-mono text-[#FA5D19] font-medium">{selectedFormat}</span>
                  </div>
                </div>
              </div>

              {/* 5. Range Component */}
              <div className="firecrawl-card flex flex-col gap-4 md:col-span-2">
                <div className="flex items-center justify-between border-b border-[#E5E7EB] pb-3">
                  <h3 className="typography-headline-sm">5. Range (`Range` / `Slider`)</h3>
                  <span className="typography-micro uppercase tracking-wider text-[#6B7280] bg-[#F9F9F9] px-2 py-0.5 rounded border border-[#E5E7EB]">
                    Primitive
                  </span>
                </div>
                <p className="typography-body-sm text-[#6B7280]">
                  Continuous slider control with orange active track fill and numeric badge readout.
                </p>
                <div className="flex flex-col gap-4 bg-[#F9F9F9] p-6 rounded-lg border border-[#E5E7EB]">
                  <Range
                    id="range-demo"
                    label="Crawl Concurrency Level"
                    value={rangeVal}
                    min={1}
                    max={100}
                    step={1}
                    onChange={setRangeVal}
                  />
                  <div className="p-3 bg-[#FFFFFF] rounded-xl border border-[#E5E7EB] text-sm flex items-center justify-between">
                    <span className="text-[#6B7280]">Current Concurrency Value:</span>
                    <span className="font-mono text-[#FA5D19] font-bold text-base">{rangeVal}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        ) : (
          /* A2UI Protocol Sandbox Tab */
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            {/* Left Column: JSON Editor */}
            <div className="lg:col-span-5 flex flex-col gap-4">
              <div className="flex items-center justify-between">
                <h3 className="typography-headline-sm">A2UI JSON Message Input</h3>
                <span className="typography-micro text-[#6B7280]">v0.9 Protocol</span>
              </div>
              <div className="relative">
                <textarea
                  value={jsonInput}
                  onChange={(e) => handleJsonUpdate(e.target.value)}
                  rows={20}
                  className="w-full font-mono text-xs p-4 bg-[#262626] text-[#F9F9F9] rounded-xl outline-none focus:ring-2 focus:ring-[#FA5D19] leading-relaxed resize-none"
                />
                {jsonError && (
                  <div className="mt-2 p-3 bg-[#DC2626]/10 border border-[#DC2626] text-[#DC2626] rounded-lg typography-body-sm">
                    {jsonError}
                  </div>
                )}
              </div>
            </div>

            {/* Right Column: Live Rendered Surface & Data Model Inspection */}
            <div className="lg:col-span-7 flex flex-col gap-6">
              {/* Live Surface Panel */}
              <div className="firecrawl-card flex flex-col gap-4">
                <div className="flex items-center justify-between border-b border-[#E5E7EB] pb-3">
                  <div className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full bg-[#FA5D19] animate-pulse"></span>
                    <h3 className="typography-headline-sm">Live A2UI Rendered Surface</h3>
                  </div>
                  <span className="typography-micro text-[#6B7280] font-mono">
                    surfaceId: {surfaceState.surfaceId}
                  </span>
                </div>

                <div className="p-4 bg-[#F9F9F9] rounded-xl border border-[#E5E7EB]">
                  <A2uiRenderer
                    surface={surfaceState}
                    onDataModelChange={updateSandboxDataModel}
                    onAction={logAction}
                  />
                </div>
              </div>

              {/* Data Model Inspection & Action Logs */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Real-time Data Model */}
                <div className="firecrawl-card flex flex-col gap-2">
                  <h4 className="typography-label-md text-[#6B7280]">Data Model State</h4>
                  <pre className="font-mono text-xs p-3 bg-[#F9F9F9] rounded-lg border border-[#E5E7EB] overflow-x-auto text-[#262626]">
                    {JSON.stringify(surfaceState.dataModel, null, 2)}
                  </pre>
                </div>

                {/* Dispatched Actions Window */}
                <div className="firecrawl-card flex flex-col gap-2">
                  <h4 className="typography-label-md text-[#6B7280]">Action Event Stream</h4>
                  <div className="font-mono text-xs p-3 bg-[#F9F9F9] rounded-lg border border-[#E5E7EB] h-40 overflow-y-auto flex flex-col gap-1.5">
                    {actionLogs.length === 0 ? (
                      <span className="text-[#6B7280] italic">Interact with components to log events...</span>
                    ) : (
                      actionLogs.map((log, idx) => (
                        <div key={idx} className="border-b border-[#E5E7EB] pb-1 last:border-none">
                          <span className="text-[#6B7280]">{log.timestamp}</span>{' '}
                          <span className="text-[#FA5D19] font-semibold">[{log.action}]</span>{' '}
                          <span className="text-[#262626]">{log.componentId}</span>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
