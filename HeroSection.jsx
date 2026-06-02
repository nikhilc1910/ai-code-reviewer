/**
 * HeroSection — Mainframe® interactive hero
 *
 * Stack: React · Tailwind CSS · motion/react · lucide-react
 *
 * Usage:
 *   import HeroSection from "./HeroSection";
 *   <HeroSection />
 *
 * Tailwind config prerequisite — add Inter to your CSS:
 *   @import url('https://fonts.googleapis.com/css2?family=Inter:ital,opsz,wght@0,14..32,100..900;1,14..32,100..900&display=swap');
 *   :root { --font-sans: 'Inter', sans-serif; }
 *
 *   @keyframes blink {
 *     0%, 100% { opacity: 1; }
 *     50%       { opacity: 0; }
 *   }
 *   .animate-blink { animation: blink 1s step-end infinite; }
 */

import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "motion/react";
import { Check } from "lucide-react";

// ─── Typewriter Hook ──────────────────────────────────────────────────────────
/**
 * Incrementally reveals `text` one character at a time.
 *
 * @param {string}  text        - Full string to type out
 * @param {number}  speed       - Milliseconds between each character (default 38)
 * @param {number}  startDelay  - Milliseconds before typing begins (default 600)
 * @returns {{ displayed: string, done: boolean }}
 */
function useTypewriter(text, speed = 38, startDelay = 600) {
  const [displayed, setDisplayed] = useState("");
  const [done, setDone] = useState(false);

  useEffect(() => {
    setDisplayed("");
    setDone(false);

    const startTimer = setTimeout(() => {
      let i = 0;
      const tick = setInterval(() => {
        i++;
        setDisplayed(text.slice(0, i));
        if (i >= text.length) {
          clearInterval(tick);
          setDone(true);
        }
      }, speed);
      return () => clearInterval(tick);
    }, startDelay);

    return () => clearTimeout(startTimer);
  }, [text, speed, startDelay]);

  return { displayed, done };
}

// ─── Background Video ─────────────────────────────────────────────────────────
function BackgroundVideo() {
  const ref = useRef(null);

  // Desktop: scrub video on mouse move
  useEffect(() => {
    const video = ref.current;
    if (!video) return;

    let prevX = null;
    let targetTime = 0;

    const onSeeked = () => {};

    const onMouseMove = (e) => {
      if (window.innerWidth < 1024) return;           // desktop only
      const x = e.clientX;
      if (prevX === null) { prevX = x; return; }
      const delta = x - prevX;
      prevX = x;
      if (!video.duration) return;
      targetTime += (delta / window.innerWidth) * 0.8 * video.duration;
      targetTime = Math.max(0, Math.min(video.duration, targetTime));
      video.currentTime = targetTime;
    };

    video.addEventListener("seeked", onSeeked);
    window.addEventListener("mousemove", onMouseMove);
    return () => {
      video.removeEventListener("seeked", onSeeked);
      window.removeEventListener("mousemove", onMouseMove);
    };
  }, []);

  // Mobile: trigger normal autoplay
  useEffect(() => {
    const video = ref.current;
    if (!video) return;
    const trigger = () => {
      if (window.innerWidth < 1024) {
        video.autoplay = true;
        video.play().catch(() => {});
      }
    };
    trigger();
    window.addEventListener("resize", trigger);
    return () => window.removeEventListener("resize", trigger);
  }, []);

  return (
    <div className="order-last lg:order-none relative lg:absolute lg:inset-0 lg:z-0 overflow-hidden pointer-events-none w-full aspect-square md:aspect-video lg:aspect-auto lg:h-full bg-neutral-50 lg:bg-transparent">
      <video
        ref={ref}
        muted
        playsInline
        preload="auto"
        className="w-full h-full object-cover object-right lg:object-right-bottom"
      >
        <source
          src="https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260601_110537_3a579fa0-7bbc-4d94-9d25-0e816c7840f5.mp4"
          type="video/mp4"
        />
      </video>
    </div>
  );
}

// ─── Navbar ───────────────────────────────────────────────────────────────────
function Navbar() {
  const [open, setOpen] = useState(false);
  const links = ["Labs", "Studio", "Openings", "Shop"];

  return (
    <>
      <header className="fixed top-0 inset-x-0 z-10 px-5 sm:px-8 py-4 sm:py-5 flex flex-row justify-between items-center bg-transparent">
        {/* Logo */}
        <div className="flex flex-row gap-3 items-end">
          <span className="text-[21px] sm:text-[26px] tracking-tight text-black font-medium select-none">
            Mainframe&reg;
          </span>
          <span className="text-[25px] sm:text-[30px] text-black select-none tracking-[-0.02em] font-medium leading-none mb-1">
            &#10033;
          </span>
        </div>

        {/* Desktop nav */}
        <nav className="hidden md:flex flex-row items-center text-[23px] text-black">
          {links.map((link, i) => (
            <span key={link} className="flex items-center">
              <a href="#" className="hover:opacity-60 transition-opacity">
                {link}
              </a>
              {i < links.length - 1 && (
                <span className="opacity-40">,&nbsp;</span>
              )}
            </span>
          ))}
        </nav>

        {/* Desktop CTA */}
        <a
          href="#"
          className="hidden md:block text-[23px] text-black underline underline-offset-2 hover:opacity-60 transition-opacity"
        >
          Get in touch
        </a>

        {/* Mobile hamburger — sits above the overlay (z-20 vs overlay z-[9]) */}
        <button
          className="md:hidden relative z-20 flex flex-col gap-[5px] justify-center items-center w-8 h-8"
          onClick={() => setOpen((v) => !v)}
          aria-label={open ? "Close menu" : "Open menu"}
        >
          <span
            className={`block w-6 h-[2px] bg-black transition-all duration-300 ${
              open ? "rotate-45 translate-y-[7px]" : ""
            }`}
          />
          <span
            className={`block w-6 h-[2px] bg-black transition-all duration-300 ${
              open ? "opacity-0" : ""
            }`}
          />
          <span
            className={`block w-6 h-[2px] bg-black transition-all duration-300 ${
              open ? "-rotate-45 -translate-y-[7px]" : ""
            }`}
          />
        </button>
      </header>

      {/* Mobile full-screen overlay — rendered as sibling to avoid stacking-context clash */}
      <div
        className={`md:hidden fixed inset-0 z-[9] bg-white/95 backdrop-blur-sm flex flex-col items-center justify-center gap-8 transition-all duration-300 ${
          open ? "opacity-100 pointer-events-auto" : "opacity-0 pointer-events-none"
        }`}
      >
        {links.map((link) => (
          <a
            key={link}
            href="#"
            onClick={() => setOpen(false)}
            className="text-3xl text-black hover:opacity-60 transition-opacity"
          >
            {link}
          </a>
        ))}
        <a
          href="#"
          onClick={() => setOpen(false)}
          className="text-3xl text-black underline underline-offset-2 hover:opacity-60 transition-opacity"
        >
          Get in touch
        </a>
      </div>
    </>
  );
}

// ─── Hero Section ─────────────────────────────────────────────────────────────
const SERVICE_OPTIONS = ["Brand", "Digital", "Campaign", "Other"];

export default function HeroSection() {
  const { displayed, done } = useTypewriter(
    "we'd love to\nhear from you!",
    38,
    600,
  );
  const [selectedServices, setSelectedServices] = useState([]);

  const toggle = (s) =>
    setSelectedServices((prev) =>
      prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s],
    );

  return (
    <>
      {/* Font + blink keyframe — inject once at the root */}
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Inter:ital,opsz,wght@0,14..32,100..900;1,14..32,100..900&display=swap');

        @keyframes blink {
          0%, 100% { opacity: 1; }
          50%       { opacity: 0; }
        }
        .animate-blink { animation: blink 1s step-end infinite; }
      `}</style>

      <div
        className="relative bg-white text-neutral-900 font-sans selection:bg-[#EAECE9] selection:text-[#1C2E1E] antialiased overflow-x-hidden flex flex-col lg:block lg:min-h-screen"
        style={{ fontFamily: "'Inter', sans-serif" }}
      >
        {/* ── Navbar ───────────────────────────────────────── */}
        <Navbar />

        {/* ── Background video (desktop: absolute; mobile: in-flow) ── */}
        <BackgroundVideo />

        {/* ── Content layer ────────────────────────────────── */}
        <div className="relative z-10 flex flex-col order-first lg:order-none w-full bg-white lg:bg-transparent pb-8 lg:pb-0 lg:min-h-screen">
          <main
            id="spade-hero"
            className="w-full max-w-7xl mx-auto px-6 py-12 flex-1 flex flex-col justify-center"
          >
            {/* Headline with typewriter */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6 }}
            >
              <h1 className="text-5xl md:text-6xl lg:text-[76px] font-normal tracking-tight text-black leading-[1.08] mb-8 select-none w-full whitespace-pre-wrap">
                {displayed}
                {!done && (
                  <span className="inline-block w-[2px] h-[1.1em] bg-black align-middle ml-[2px] animate-blink" />
                )}
              </h1>
            </motion.div>

            {/* Description */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.1 }}
            >
              <p className="text-lg md:text-xl text-[#5A635A] leading-relaxed font-normal mb-14 max-w-2xl">
                Whether you have questions, feedback, <br />
                drop us a message and we'll get back to you as soon as possible.
              </p>
            </motion.div>

            {/* Service pills */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.2 }}
            >
              <p className="text-2xl font-medium tracking-tight mb-2">
                What sort of service?
              </p>
              <p
                className="text-[#738273] mb-8"
                style={{ opacity: 0.85 }}
              >
                Select all that apply
              </p>

              <div className="flex flex-wrap gap-3 mb-6">
                {SERVICE_OPTIONS.map((s) => {
                  const active = selectedServices.includes(s);
                  return (
                    <motion.button
                      key={s}
                      onClick={() => toggle(s)}
                      whileTap={{ scale: 0.96 }}
                      className={`flex items-center gap-2 px-5 py-2.5 rounded-full text-base font-medium transition-all duration-200 ${
                        active
                          ? "bg-[#1C2E1E] text-white shadow-md shadow-emerald-950/5 transform"
                          : "bg-white text-[#1C2E1E] border border-[#F1F3F1] hover:bg-[#F1F3F1]/55"
                      }`}
                    >
                      <AnimatePresence>
                        {active && (
                          <motion.span
                            initial={{ scale: 0, opacity: 0 }}
                            animate={{ scale: 1, opacity: 1 }}
                            exit={{ scale: 0, opacity: 0 }}
                            transition={{
                              type: "spring",
                              stiffness: 300,
                              damping: 20,
                            }}
                            className="flex items-center"
                          >
                            <Check size={14} strokeWidth={2.5} />
                          </motion.span>
                        )}
                      </AnimatePresence>
                      {s}
                    </motion.button>
                  );
                })}
              </div>

              {/* Contingent feedback banner */}
              <AnimatePresence mode="wait">
                {selectedServices.length === 0 ? (
                  <motion.p
                    key="empty"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 0.5 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.2 }}
                    className="text-xs italic text-neutral-500"
                  >
                    Please click to select services above.
                  </motion.p>
                ) : (
                  <motion.div
                    key="selected"
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    exit={{ opacity: 0, height: 0 }}
                    transition={{ type: "spring", stiffness: 300, damping: 30 }}
                    className="overflow-hidden"
                  >
                    <div className="bg-[#FAFBF9] border border-[#EEF0EE] rounded-2xl px-5 py-4 flex items-center justify-between gap-4">
                      <p className="text-sm text-[#1C2E1E]">
                        Ready to inquire about:{" "}
                        <span className="font-medium">
                          {selectedServices.join(", ")}
                        </span>
                      </p>
                      <button className="shrink-0 text-[#4D6D47] uppercase text-xs font-semibold tracking-wider flex items-center gap-1 hover:opacity-70 transition-opacity">
                        Let's Go <span aria-hidden="true">→</span>
                      </button>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>
          </main>
        </div>
      </div>
    </>
  );
}
