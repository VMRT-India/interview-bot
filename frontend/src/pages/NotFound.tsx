import { Link } from "react-router-dom";
import { Layout } from "../components/layout/Layout";

export default function NotFound() {
  return (
    <Layout showFooter={false}>
      <div className="flex flex-col items-center pt-24 text-center">
        <h1 className="text-3xl font-semibold text-white">Page not found</h1>
        <Link to="/" className="mt-4 text-[color:var(--color-accent-soft)]">
          Back home
        </Link>
      </div>
    </Layout>
  );
}
