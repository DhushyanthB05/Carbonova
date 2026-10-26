import React from 'react';

export type PreloadableComponent<T extends React.ComponentType<any>> = React.FC<React.ComponentProps<T>> & {
  preload: () => Promise<{ default: T }>;
};

/**
 * Creates a lazy-loaded component with a .preload() method.
 * Allows components to be dynamically split into separate chunks for production,
 * while allowing tests and routers to eagerly preload them when needed.
 */
export function lazyWithPreload<T extends React.ComponentType<any>>(
  factory: () => Promise<any>,
  exportName?: string
): PreloadableComponent<T> {
  let loadedComponent: T | null = null;
  let factoryPromise: Promise<{ default: T }> | null = null;

  const preload = () => {
    if (!factoryPromise) {
      factoryPromise = factory().then((module: any) => {
        const comp = exportName ? module[exportName] : (module.default || Object.values(module)[0]);
        loadedComponent = comp as T;
        return { default: comp as T };
      });
    }
    return factoryPromise;
  };

  const LazyComponent = React.lazy(preload);

  const Component: React.FC<React.ComponentProps<T>> = (props) => {
    if (loadedComponent) {
      const Comp = loadedComponent;
      return <Comp {...props} />;
    }
    return <LazyComponent {...props} />;
  };

  (Component as PreloadableComponent<T>).preload = preload;

  return Component as PreloadableComponent<T>;
}
