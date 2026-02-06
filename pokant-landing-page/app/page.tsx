"use client"

import { useState, useEffect, useRef } from "react"
import Link from "next/link"
import { ArrowRight, ArrowDown, Menu, X, Check, Mic, Waves, Shield, Zap, BarChart3, Code2, Clock, Globe, Cpu, Volume2 } from "lucide-react"
import { Button } from "@/components/ui/button"

function useInView(threshold = 0.1) {
  const ref = useRef<HTMLDivElement>(null)
  const [isInView, setIsInView] = useState(false)

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsInView(true)
        }
      },
      { threshold }
    )

    if (ref.current) {
      observer.observe(ref.current)
    }

    return () => observer.disconnect()
  }, [threshold])

  return { ref, isInView }
}

// Animated typing effect for hero
function TypeWriter({ words, className }: { words: string[]; className?: string }) {
  const [currentWordIndex, setCurrentWordIndex] = useState(0)
  const [currentText, setCurrentText] = useState("")
  const [isDeleting, setIsDeleting] = useState(false)

  useEffect(() => {
    const word = words[currentWordIndex]
    const timeout = setTimeout(() => {
      if (!isDeleting) {
        if (currentText.length < word.length) {
          setCurrentText(word.slice(0, currentText.length + 1))
        } else {
          setTimeout(() => setIsDeleting(true), 2000)
        }
      } else {
        if (currentText.length > 0) {
          setCurrentText(word.slice(0, currentText.length - 1))
        } else {
          setIsDeleting(false)
          setCurrentWordIndex((prev) => (prev + 1) % words.length)
        }
      }
    }, isDeleting ? 50 : 100)

    return () => clearTimeout(timeout)
  }, [currentText, isDeleting, currentWordIndex, words])

  return (
    <span className={className}>
      {currentText}
      <span className="animate-pulse">|</span>
    </span>
  )
}

// Animated waveform visualization
function WaveformVisualization() {
  const bars = 48
  const [heights, setHeights] = useState<number[]>([])

  useEffect(() => {
    // Initialize with random heights
    setHeights(Array.from({ length: bars }, () => Math.random() * 100))

    const interval = setInterval(() => {
      setHeights((prev) =>
        prev.map((h) => {
          const change = (Math.random() - 0.5) * 30
          return Math.max(10, Math.min(100, h + change))
        })
      )
    }, 100)

    return () => clearInterval(interval)
  }, [])

  if (heights.length === 0) {
    return (
      <div className="flex items-end justify-center gap-[2px] h-32">
        {Array.from({ length: bars }).map((_, i) => (
          <div
            key={i}
            className="w-1 rounded-full bg-primary/30"
            style={{ height: "50%" }}
          />
        ))}
      </div>
    )
  }

  return (
    <div className="flex items-end justify-center gap-[2px] h-32">
      {heights.map((height, i) => (
        <div
          key={i}
          className="w-1 rounded-full bg-gradient-to-t from-primary via-primary to-teal-400 transition-all duration-100"
          style={{ height: `${height}%` }}
        />
      ))}
    </div>
  )
}

// Floating metrics that animate in
function FloatingMetric({ label, value, delay }: { label: string; value: string; delay: number }) {
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const timeout = setTimeout(() => setVisible(true), delay)
    return () => clearTimeout(timeout)
  }, [delay])

  return (
    <div
      className={`bg-card/60 backdrop-blur-xl border border-border/40 rounded-xl px-4 py-3 transition-all duration-700 ${
        visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"
      }`}
    >
      <div className="text-xs text-muted-foreground mb-1">{label}</div>
      <div className="text-lg font-semibold text-foreground">{value}</div>
    </div>
  )
}

const capabilities = [
  {
    icon: Volume2,
    title: "Noise Resilience",
    description: "Test in 60-110dB environments from call centers to construction sites",
  },
  {
    icon: Globe,
    title: "Accent & Dialect",
    description: "Evaluate across 50+ accents and regional speech patterns",
  },
  {
    icon: Clock,
    title: "Latency Analysis",
    description: "Measure response times under real network conditions",
  },
  {
    icon: Cpu,
    title: "Edge Cases",
    description: "Stress test with interruptions, overlapping speech, and more",
  },
]

const howItWorks = [
  {
    icon: Code2,
    number: "01",
    title: "Send Your Audio",
    description: "POST audio samples with test parameters via our REST API or SDK.",
  },
  {
    icon: Waves,
    number: "02",
    title: "Run Test Suite",
    description: "We apply comprehensive scenarios: noise, accents, latency, and edge cases.",
  },
  {
    icon: BarChart3,
    number: "03",
    title: "Get Detailed Reports",
    description: "Receive accuracy metrics, failure analysis, and improvement suggestions.",
  },
  {
    icon: Shield,
    number: "04",
    title: "Ship Confidently",
    description: "Deploy knowing your voice AI handles real-world conditions.",
  },
]

const testimonials = [
  {
    quote: "Pokant found accuracy drops we never knew existed. Our users in noisy environments are finally having great experiences.",
    author: "Sarah Chen",
    role: "ML Lead at VoiceBot",
    avatar: "SC",
  },
  {
    quote: "The accent testing alone saved us months of user complaints. Integration took 15 minutes.",
    author: "Marcus Rodriguez",
    role: "Staff Engineer at AudioAI",
    avatar: "MR",
  },
  {
    quote: "We run every PR through Pokant now. Support tickets dropped 60% after launch.",
    author: "Aisha Patel",
    role: "VP Engineering at SpeakEasy",
    avatar: "AP",
  },
]

const pricingTiers = [
  {
    name: "Developer",
    price: "$99",
    period: "/mo",
    description: "For individual developers and small projects",
    features: [
      "1,000 evaluations/month",
      "10 test scenarios",
      "Standard latency",
      "Community support",
      "REST API access",
    ],
    cta: "Start Free Trial",
    highlighted: false,
  },
  {
    name: "Team",
    price: "$299",
    period: "/mo",
    description: "For teams shipping to production",
    features: [
      "10,000 evaluations/month",
      "All scenarios + custom",
      "Priority latency (<500ms)",
      "Email + Slack support",
      "CI/CD integrations",
      "Detailed analytics",
    ],
    cta: "Start Free Trial",
    highlighted: true,
  },
  {
    name: "Enterprise",
    price: "Custom",
    period: "",
    description: "For large-scale deployments",
    features: [
      "Unlimited evaluations",
      "Custom scenario builder",
      "Dedicated support",
      "On-premise option",
      "SLA guarantees",
      "Advanced reporting",
    ],
    cta: "Contact Sales",
    highlighted: false,
  },
]

export default function LandingPage() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [heroLoaded, setHeroLoaded] = useState(false)
  const capabilitiesRef = useInView()
  const howItWorksRef = useInView()
  const codeRef = useInView()
  const testimonialsRef = useInView()
  const pricingRef = useInView()

  useEffect(() => {
    setHeroLoaded(true)
  }, [])

  return (
    <div className="min-h-screen bg-background">
      {/* Navigation */}
      <nav className="fixed top-0 left-0 right-0 z-50 bg-background/80 backdrop-blur-xl border-b border-border/40">
        <div className="max-w-7xl mx-auto px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <Link href="/" className="text-foreground font-bold text-xl tracking-tight">
              pokant
            </Link>

            <div className="hidden md:flex items-center gap-8">
              <Link href="#capabilities" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
                Capabilities
              </Link>
              <Link href="#how-it-works" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
                How It Works
              </Link>
              <Link href="#pricing" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
                Pricing
              </Link>
              <Link href="#" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
                Docs
              </Link>
            </div>

            <div className="hidden md:flex items-center gap-4">
              <Link href="/signin.html" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
                Sign in
              </Link>
              <Button size="sm" className="bg-primary hover:bg-primary/90 text-primary-foreground">
                Get Started
              </Button>
            </div>

            <button className="md:hidden text-foreground" onClick={() => setMobileMenuOpen(!mobileMenuOpen)}>
              {mobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
            </button>
          </div>
        </div>

        {mobileMenuOpen && (
          <div className="md:hidden bg-background/95 backdrop-blur-xl border-t border-border/40">
            <div className="px-6 py-6 space-y-4">
              <Link href="#capabilities" className="block text-sm text-muted-foreground hover:text-foreground">
                Capabilities
              </Link>
              <Link href="#how-it-works" className="block text-sm text-muted-foreground hover:text-foreground">
                How It Works
              </Link>
              <Link href="#pricing" className="block text-sm text-muted-foreground hover:text-foreground">
                Pricing
              </Link>
              <Link href="#" className="block text-sm text-muted-foreground hover:text-foreground">
                Docs
              </Link>
              <hr className="border-border/40" />
              <Button size="sm" className="w-full bg-primary hover:bg-primary/90 text-primary-foreground">
                Get Started
              </Button>
            </div>
          </div>
        )}
      </nav>

      {/* Hero Section - Full Screen */}
      <section className="relative min-h-screen flex flex-col">
        {/* Video Background */}
        <div className="absolute inset-0 -z-10 overflow-hidden">
          <video
            autoPlay
            loop
            muted
            playsInline
            className="absolute inset-0 w-full h-full object-cover scale-105"
          >
            <source src="/space-animation.mp4" type="video/mp4" />
          </video>
          <div className="absolute inset-0 bg-gradient-to-b from-background/40 via-background/70 to-background" />
          <div className="absolute inset-0 bg-gradient-to-r from-background/80 via-transparent to-background/80" />
        </div>

        {/* Hero Content */}
        <div className="flex-1 flex items-center justify-center px-6 lg:px-8 pt-16">
          <div className="max-w-5xl mx-auto w-full">
            <div className="grid lg:grid-cols-2 gap-12 items-center">
              {/* Left Column - Text */}
              <div>
                <div
                  className={`transition-all duration-1000 delay-100 ${
                    heroLoaded ? "opacity-100 translate-y-0" : "opacity-0 translate-y-8"
                  }`}
                >
                  <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-primary/10 border border-primary/20 text-primary text-xs font-medium mb-6">
                    <Zap className="w-3 h-3" />
                    Comprehensive Voice AI Testing
                  </div>
                </div>

                <h1
                  className={`text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tight text-foreground mb-6 leading-[1.1] transition-all duration-1000 delay-200 ${
                    heroLoaded ? "opacity-100 translate-y-0" : "opacity-0 translate-y-8"
                  }`}
                >
                  Test your voice AI
                  <br />
                  <span className="text-primary">
                    <TypeWriter words={["in real noise", "across accents", "at scale", "before launch"]} />
                  </span>
                </h1>

                <p
                  className={`text-lg text-muted-foreground mb-8 max-w-lg leading-relaxed transition-all duration-1000 delay-300 ${
                    heroLoaded ? "opacity-100 translate-y-0" : "opacity-0 translate-y-8"
                  }`}
                >
                  The complete evaluation platform for voice AI. Test noise resilience, accent coverage, latency, and edge cases before your users do.
                </p>

                <div
                  className={`flex flex-col sm:flex-row gap-4 transition-all duration-1000 delay-400 ${
                    heroLoaded ? "opacity-100 translate-y-0" : "opacity-0 translate-y-8"
                  }`}
                >
                  <Button size="lg" className="bg-primary hover:bg-primary/90 text-primary-foreground px-8 h-12">
                    Get API Key
                    <ArrowRight className="ml-2 h-4 w-4" />
                  </Button>
                  <Button size="lg" variant="outline" className="border-border hover:bg-muted/50 h-12 bg-transparent">
                    View Documentation
                  </Button>
                </div>
              </div>

              {/* Right Column - Visualization */}
              <div
                className={`relative transition-all duration-1000 delay-500 ${
                  heroLoaded ? "opacity-100 translate-y-0 scale-100" : "opacity-0 translate-y-8 scale-95"
                }`}
              >
                <div className="bg-card/40 backdrop-blur-xl border border-border/40 rounded-2xl p-6 shadow-2xl">
                  <div className="flex items-center gap-2 mb-6">
                    <div className="w-3 h-3 rounded-full bg-red-500/80" />
                    <div className="w-3 h-3 rounded-full bg-yellow-500/80" />
                    <div className="w-3 h-3 rounded-full bg-green-500/80" />
                    <span className="text-xs text-muted-foreground font-mono ml-auto">Live Analysis</span>
                  </div>

                  <WaveformVisualization />

                  <div className="grid grid-cols-3 gap-3 mt-6">
                    <FloatingMetric label="Accuracy" value="94.2%" delay={800} />
                    <FloatingMetric label="Latency" value="124ms" delay={1000} />
                    <FloatingMetric label="Scenarios" value="47/50" delay={1200} />
                  </div>
                </div>

                {/* Floating badges */}
                <div
                  className={`absolute -top-4 -right-4 bg-green-500/10 border border-green-500/20 rounded-lg px-3 py-1.5 transition-all duration-1000 delay-700 ${
                    heroLoaded ? "opacity-100 translate-y-0" : "opacity-0 -translate-y-4"
                  }`}
                >
                  <span className="text-xs font-medium text-green-500">All Tests Passing</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Scroll Indicator */}
        <div
          className={`absolute bottom-8 left-1/2 -translate-x-1/2 transition-all duration-1000 delay-1000 ${
            heroLoaded ? "opacity-100" : "opacity-0"
          }`}
        >
          <div className="flex flex-col items-center gap-2 text-muted-foreground">
            <span className="text-xs">Scroll to explore</span>
            <ArrowDown className="w-4 h-4 animate-bounce" />
          </div>
        </div>
      </section>

      {/* Capabilities Section */}
      <section id="capabilities" className="py-24 px-6 lg:px-8" ref={capabilitiesRef.ref}>
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-16">
            <h2
              className={`text-3xl lg:text-4xl font-bold text-foreground mb-4 transition-all duration-700 ${
                capabilitiesRef.isInView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-8"
              }`}
            >
              Complete Testing Coverage
            </h2>
            <p
              className={`text-lg text-muted-foreground max-w-2xl mx-auto transition-all duration-700 delay-100 ${
                capabilitiesRef.isInView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-8"
              }`}
            >
              Every dimension of voice AI performance, measured and analyzed
            </p>
          </div>

          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-6">
            {capabilities.map((item, i) => (
              <div
                key={item.title}
                className={`group bg-card/40 backdrop-blur-sm border border-border/40 rounded-2xl p-6 transition-all duration-700 hover:border-primary/40 hover:-translate-y-1 ${
                  capabilitiesRef.isInView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-8"
                }`}
                style={{ transitionDelay: `${i * 100}ms` }}
              >
                <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center mb-4 group-hover:bg-primary/20 transition-colors">
                  <item.icon className="w-6 h-6 text-primary" />
                </div>
                <h3 className="text-lg font-semibold text-foreground mb-2">{item.title}</h3>
                <p className="text-sm text-muted-foreground leading-relaxed">{item.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* How It Works */}
      <section id="how-it-works" className="py-24 px-6 lg:px-8 bg-muted/30" ref={howItWorksRef.ref}>
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-16">
            <h2
              className={`text-3xl lg:text-4xl font-bold text-foreground mb-4 transition-all duration-700 ${
                howItWorksRef.isInView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-8"
              }`}
            >
              How It Works
            </h2>
            <p
              className={`text-lg text-muted-foreground max-w-2xl mx-auto transition-all duration-700 delay-100 ${
                howItWorksRef.isInView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-8"
              }`}
            >
              From integration to production confidence in four steps
            </p>
          </div>

          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-6">
            {howItWorks.map((item, i) => (
              <div
                key={item.title}
                className={`group relative bg-card/40 backdrop-blur-sm border border-border/40 rounded-2xl p-6 transition-all duration-700 hover:border-primary/40 hover:-translate-y-1 ${
                  howItWorksRef.isInView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-8"
                }`}
                style={{ transitionDelay: `${i * 150}ms` }}
              >
                <div className="text-5xl font-bold text-primary/10 mb-4 font-mono">{item.number}</div>
                <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center mb-4 group-hover:bg-primary/20 transition-colors">
                  <item.icon className="w-5 h-5 text-primary" />
                </div>
                <h3 className="text-lg font-semibold text-foreground mb-2">{item.title}</h3>
                <p className="text-sm text-muted-foreground leading-relaxed">{item.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Code Example */}
      <section className="py-24 px-6 lg:px-8" ref={codeRef.ref}>
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-12">
            <h2
              className={`text-3xl lg:text-4xl font-bold text-foreground mb-4 transition-all duration-700 ${
                codeRef.isInView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-8"
              }`}
            >
              Simple Integration
            </h2>
            <p
              className={`text-lg text-muted-foreground transition-all duration-700 delay-100 ${
                codeRef.isInView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-8"
              }`}
            >
              Start testing in minutes with our REST API
            </p>
          </div>

          <div
            className={`transition-all duration-1000 delay-200 ${
              codeRef.isInView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-8"
            }`}
          >
            <div className="bg-[#0d1117] rounded-2xl overflow-hidden border border-border/20 shadow-2xl">
              <div className="flex items-center justify-between px-6 py-4 bg-[#161b22] border-b border-border/20">
                <span className="text-sm text-gray-400 font-mono">test-voice-ai.ts</span>
                <div className="flex gap-2">
                  <div className="w-3 h-3 rounded-full bg-[#ff5f56]" />
                  <div className="w-3 h-3 rounded-full bg-[#ffbd2e]" />
                  <div className="w-3 h-3 rounded-full bg-[#27ca40]" />
                </div>
              </div>
              <pre className="p-6 overflow-x-auto text-sm">
                <code className="text-gray-300 font-mono leading-relaxed">
{`// Run comprehensive voice AI tests
`}<span className="text-[#ff7b72]">const</span>{` results = `}<span className="text-[#ff7b72]">await</span>{` pokant.`}<span className="text-[#d2a8ff]">test</span>{`({
  `}<span className="text-[#79c0ff]">audio</span>{`: audioFile,
  `}<span className="text-[#79c0ff]">scenarios</span>{`: [`}<span className="text-[#a5d6ff]">'noise'</span>{`, `}<span className="text-[#a5d6ff]">'accents'</span>{`, `}<span className="text-[#a5d6ff]">'latency'</span>{`, `}<span className="text-[#a5d6ff]">'edge_cases'</span>{`],
  `}<span className="text-[#79c0ff]">model</span>{`: `}<span className="text-[#a5d6ff]">'whisper-large-v3'</span>{`
});

`}<span className="text-[#8b949e]">// Response</span>{`
{
  `}<span className="text-[#a5d6ff]">"overall_score"</span>{`: `}<span className="text-[#79c0ff]">0.94</span>{`,
  `}<span className="text-[#a5d6ff]">"noise_resilience"</span>{`: `}<span className="text-[#79c0ff]">0.87</span>{`,
  `}<span className="text-[#a5d6ff]">"accent_coverage"</span>{`: `}<span className="text-[#79c0ff]">0.96</span>{`,
  `}<span className="text-[#a5d6ff]">"latency_p95"</span>{`: `}<span className="text-[#79c0ff]">142</span>{`,
  `}<span className="text-[#a5d6ff]">"edge_cases_passed"</span>{`: `}<span className="text-[#79c0ff]">47</span>{`/`}<span className="text-[#79c0ff]">50</span>{`
}`}
                </code>
              </pre>
            </div>
          </div>
        </div>
      </section>

      {/* Testimonials */}
      <section className="py-24 px-6 lg:px-8 bg-muted/30" ref={testimonialsRef.ref}>
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-16">
            <h2
              className={`text-3xl lg:text-4xl font-bold text-foreground mb-4 transition-all duration-700 ${
                testimonialsRef.isInView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-8"
              }`}
            >
              Trusted by ML Teams
            </h2>
            <p
              className={`text-lg text-muted-foreground transition-all duration-700 delay-100 ${
                testimonialsRef.isInView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-8"
              }`}
            >
              Companies shipping production voice AI rely on Pokant
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-6">
            {testimonials.map((item, i) => (
              <div
                key={item.author}
                className={`bg-card/40 backdrop-blur-sm border border-border/40 rounded-2xl p-8 transition-all duration-700 hover:border-primary/40 ${
                  testimonialsRef.isInView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-8"
                }`}
                style={{ transitionDelay: `${i * 150}ms` }}
              >
                <div className="flex items-center gap-3 mb-6">
                  <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center text-primary font-semibold text-sm">
                    {item.avatar}
                  </div>
                  <div>
                    <div className="font-semibold text-foreground text-sm">{item.author}</div>
                    <div className="text-xs text-muted-foreground">{item.role}</div>
                  </div>
                </div>
                <p className="text-muted-foreground leading-relaxed">&ldquo;{item.quote}&rdquo;</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section id="pricing" className="py-24 px-6 lg:px-8" ref={pricingRef.ref}>
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-16">
            <h2
              className={`text-3xl lg:text-4xl font-bold text-foreground mb-4 transition-all duration-700 ${
                pricingRef.isInView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-8"
              }`}
            >
              Simple Pricing
            </h2>
            <p
              className={`text-lg text-muted-foreground transition-all duration-700 delay-100 ${
                pricingRef.isInView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-8"
              }`}
            >
              Start free, scale as you grow
            </p>
          </div>

          <div className="grid lg:grid-cols-3 gap-8 max-w-5xl mx-auto">
            {pricingTiers.map((tier, i) => (
              <div
                key={tier.name}
                className={`relative bg-card/40 backdrop-blur-sm border rounded-2xl p-8 transition-all duration-700 hover:-translate-y-1 ${
                  tier.highlighted
                    ? "border-primary/60 shadow-xl shadow-primary/10 lg:scale-105"
                    : "border-border/40"
                } ${pricingRef.isInView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-8"}`}
                style={{ transitionDelay: `${i * 150}ms` }}
              >
                {tier.highlighted && (
                  <div className="absolute -top-4 left-1/2 -translate-x-1/2 px-4 py-1 bg-primary text-primary-foreground text-xs font-medium rounded-full">
                    Most Popular
                  </div>
                )}
                <div className="mb-8">
                  <h3 className="text-xl font-semibold text-foreground mb-2">{tier.name}</h3>
                  <p className="text-sm text-muted-foreground mb-4">{tier.description}</p>
                  <div className="flex items-baseline gap-1">
                    <span className="text-4xl font-bold text-foreground">{tier.price}</span>
                    <span className="text-muted-foreground">{tier.period}</span>
                  </div>
                </div>
                <ul className="space-y-3 mb-8">
                  {tier.features.map((feature) => (
                    <li key={feature} className="flex items-start gap-3 text-sm">
                      <Check className="w-4 h-4 text-primary mt-0.5 flex-shrink-0" />
                      <span className="text-muted-foreground">{feature}</span>
                    </li>
                  ))}
                </ul>
                <Button
                  className={`w-full ${
                    tier.highlighted
                      ? "bg-primary text-primary-foreground hover:bg-primary/90"
                      : "bg-primary/10 text-primary hover:bg-primary/20 border border-primary/20"
                  }`}
                >
                  {tier.cta}
                </Button>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-24 px-6 lg:px-8 border-t border-border/40 bg-muted/30">
        <div className="max-w-4xl mx-auto text-center">
          <h2 className="text-3xl lg:text-4xl font-bold text-foreground mb-4">
            Ready to test your voice AI?
          </h2>
          <p className="text-lg text-muted-foreground mb-8">
            Get started for free. No credit card required.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <Button size="lg" className="bg-primary hover:bg-primary/90 text-primary-foreground px-8 h-12">
              Get API Key
              <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
            <Button size="lg" variant="outline" className="border-border hover:bg-muted/50 h-12 bg-transparent">
              Schedule Demo
            </Button>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-border/40 py-12 px-6 lg:px-8">
        <div className="max-w-7xl mx-auto">
          <div className="grid md:grid-cols-4 gap-8 mb-8">
            <div>
              <div className="font-bold text-foreground text-lg mb-4">pokant</div>
              <p className="text-sm text-muted-foreground">
                Comprehensive voice AI testing for production
              </p>
            </div>
            <div>
              <div className="text-sm font-semibold text-foreground mb-3">Product</div>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li><Link href="#" className="hover:text-foreground transition-colors">API</Link></li>
                <li><Link href="#pricing" className="hover:text-foreground transition-colors">Pricing</Link></li>
                <li><Link href="#" className="hover:text-foreground transition-colors">Documentation</Link></li>
              </ul>
            </div>
            <div>
              <div className="text-sm font-semibold text-foreground mb-3">Company</div>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li><Link href="#" className="hover:text-foreground transition-colors">About</Link></li>
                <li><Link href="#" className="hover:text-foreground transition-colors">Blog</Link></li>
                <li><Link href="#" className="hover:text-foreground transition-colors">Careers</Link></li>
              </ul>
            </div>
            <div>
              <div className="text-sm font-semibold text-foreground mb-3">Legal</div>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li><Link href="#" className="hover:text-foreground transition-colors">Privacy</Link></li>
                <li><Link href="#" className="hover:text-foreground transition-colors">Terms</Link></li>
              </ul>
            </div>
          </div>
          <div className="pt-8 border-t border-border/40 text-center text-sm text-muted-foreground">
            &copy; 2026 Pokant. All rights reserved.
          </div>
        </div>
      </footer>
    </div>
  )
}
