import Link from "next/link"

export default function DashboardPage() {
  return (
    <div className="min-h-screen bg-[#FAFAFA] p-8">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-2xl font-bold text-[#111827] mb-2">Dashboard</h1>
        <p className="text-[#6B7280] mb-6">
          Voice AI evaluation overview. Use the links below to explore.
        </p>
        <div className="flex flex-wrap gap-4">
          <Link
            href="/"
            className="inline-flex items-center gap-2 px-5 py-2.5 bg-[#3B82F6] hover:bg-blue-600 text-white font-medium rounded-lg transition-colors"
          >
            Back to home
          </Link>
          <a
            href="/test-runs.html"
            className="inline-flex items-center gap-2 px-5 py-2.5 border border-[#E5E7EB] rounded-lg text-[#374151] hover:bg-white transition-colors"
          >
            Test Runs (static)
          </a>
        </div>
      </div>
    </div>
  )
}
