import React, { Component, ErrorInfo, ReactNode } from 'react';
import { AlertTriangle, RefreshCw, Home, ChevronDown, ChevronUp } from 'lucide-react';

interface Props {
  children: ReactNode;
  fallbackTitle?: string;
  onReset?: () => void;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
  showDetails: boolean;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
      showDetails: false,
    };
  }

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Carbonova Uncaught UI Error:', error, errorInfo);
    this.setState({ errorInfo });
  }

  handleReset = () => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
      showDetails: false,
    });
    if (this.props.onReset) {
      this.props.onReset();
    }
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-[400px] flex items-center justify-center p-6">
          <div className="bg-white rounded-2xl border border-red-150 p-8 max-w-lg w-full shadow-lg flex flex-col items-center text-center">
            {/* Warning Icon Badge */}
            <div className="w-14 h-14 rounded-2xl bg-red-50 border border-red-100 text-red-600 flex items-center justify-center mb-4">
              <AlertTriangle className="w-7 h-7" />
            </div>

            <span className="text-xs font-bold uppercase tracking-wider text-red-600 bg-red-50/80 px-2.5 py-1 rounded-full mb-2">
              Runtime Error Guard
            </span>

            <h3 className="text-lg font-bold text-slate-900 mb-2">
              {this.props.fallbackTitle || 'Rendering Interrupted'}
            </h3>

            <p className="text-xs text-slate-500 mb-6 max-w-sm leading-relaxed">
              An unexpected error occurred while rendering this section. Carbonova prevented a complete application crash to protect your data.
            </p>

            {/* Error Message Snippet */}
            {this.state.error && (
              <div className="w-full bg-slate-50 border border-slate-200 rounded-lg p-3 text-left mb-5">
                <span className="text-[10px] font-bold uppercase text-slate-400 block mb-1">
                  Exception:
                </span>
                <p className="text-xs font-mono text-red-700 break-words leading-tight">
                  {this.state.error.message || 'Unknown JavaScript exception'}
                </p>
              </div>
            )}

            {/* Actions */}
            <div className="flex flex-wrap items-center justify-center gap-3 w-full">
              <button
                type="button"
                onClick={this.handleReset}
                className="flex items-center gap-2 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold shadow-xs transition-colors"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                <span>Retry View</span>
              </button>

              <button
                type="button"
                onClick={() => {
                  window.location.href = '/';
                }}
                className="flex items-center gap-2 px-4 py-2 rounded-xl border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 text-xs font-semibold transition-colors"
              >
                <Home className="w-3.5 h-3.5 text-slate-400" />
                <span>Return to Overview</span>
              </button>
            </div>

            {/* Stack trace toggle for developers */}
            {this.state.errorInfo && (
              <div className="w-full mt-6 pt-4 border-t border-slate-100 text-left">
                <button
                  type="button"
                  onClick={() => this.setState({ showDetails: !this.state.showDetails })}
                  className="flex items-center justify-between w-full text-[11px] font-semibold text-slate-500 hover:text-slate-700"
                >
                  <span>Technical Diagnostics</span>
                  {this.state.showDetails ? (
                    <ChevronUp className="w-3.5 h-3.5" />
                  ) : (
                    <ChevronDown className="w-3.5 h-3.5" />
                  )}
                </button>

                {this.state.showDetails && (
                  <pre className="mt-2 p-3 bg-slate-900 text-slate-300 rounded-lg text-[10px] font-mono overflow-x-auto max-h-48 leading-relaxed">
                    {this.state.error?.stack}
                    {'\n'}
                    {this.state.errorInfo.componentStack}
                  </pre>
                )}
              </div>
            )}
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
