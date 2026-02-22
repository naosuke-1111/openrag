import React from 'react';
import { CenterPanel } from '../center-panel/CenterPanel';
import { LeftPanel } from '../left-panel/LeftPanel';
import { RightPanel } from '../right-panel/RightPanel';

export const SafeAreaContainer: React.FC = () => {
  return (
    <div className="safe-area-container">
      <div className="panels-container">
        {/* Left panel: Watson NLU Pipeline */}
        <div className="panel-left">
          <LeftPanel />
        </div>

        {/* Center panel: Neural Graph */}
        <div className="panel-center">
          <CenterPanel />
        </div>

        {/* Right panel: Article Queue + Classification */}
        <div className="panel-right">
          <RightPanel />
        </div>
      </div>
    </div>
  );
};
