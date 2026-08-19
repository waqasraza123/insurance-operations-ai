import Image from "next/image";
import Link from "next/link";

export function Brand() {
  return (
    <Link
      aria-label="Insurance Operations AI home"
      className="brand-link"
      href="/"
    >
      <Image
        alt=""
        aria-hidden="true"
        className="brand-mark"
        height={32}
        src="/brand-mark.png"
        width={32}
      />
      <span>Insurance Operations AI</span>
    </Link>
  );
}
