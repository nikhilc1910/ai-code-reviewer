import React from 'react';
import { SwayCanvas } from './SwayCanvas';

export const HeroSection: React.FC = () => {
  return (
    <section
      style={{
        position: 'relative',
        width: '100%',
        height: '100vh',
        overflow: 'hidden',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: '#030712',
      }}
    >
      {/* SwayCanvas background */}
      <SwayCanvas />

      {/* Main content hero panel */}
      <div
        style={{
          position: 'relative',
          zIndex: 10,
          textAlign: 'center',
          padding: '2rem',
          maxWidth: '800px',
        }}
      >
        <h1
          style={{
            fontSize: '3.5rem',
            fontWeight: 800,
            line-height: '1.2',
            color: '#ffffff',
            margin: 0,
            fontFamily: 'Outfit, sans-serif',
          }}
        >
          The Code Review /{' '}
          <span
            style={{
              background: 'linear-gradient(135deg, #ec4899 10%, #8b5cf6 50%, #06b6d4 90%)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
            }}
          >
            Your Team Deserves
          </span>
        </h1>
        <p
          style={{
            fontSize: '1.25rem',
            color: '#94a3b8',
            marginTop: '1.5rem',
            lineHeight: '1.6',
            fontFamily: 'Space Grotesk, sans-serif',
          }}
        >
          A sleek, high-precision code reviewer powered by agentic intelligence.
        </p>
      </div>
    </section>
  );
};
