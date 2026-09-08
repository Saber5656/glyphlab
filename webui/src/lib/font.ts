import { useEffect, useState } from "react";
import { apiFetch } from "./api";
import type { Artifact } from "../generated/types";

type FontState = {
    loading: boolean;
    ready: boolean;
    error?: string;
};

async function readBlobBuffer(blob: Blob): Promise<ArrayBuffer> {
    if (typeof blob.arrayBuffer === "function") return blob.arrayBuffer();
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result as ArrayBuffer);
        reader.onerror = () => reject(reader.error);
        reader.readAsArrayBuffer(blob);
    });
}

export function useProjectFont(
    projectId: string,
    artifact: Artifact | undefined,
): FontState {
    const [state, setState] = useState<FontState>({
        loading: false,
        ready: false,
    });
    useEffect(() => {
        let disposed = false;
        let installed = false;
        let face: FontFace | undefined;
        if (!artifact) {
            setState({ loading: false, ready: false });
            return;
        }
        if (typeof FontFace === "undefined" || !document.fonts) {
            setState({ loading: false, ready: false, error: "font-api" });
            return;
        }
        setState({ loading: true, ready: false });
        void apiFetch<Blob>(`/projects/${projectId}/artifacts/${artifact.id}`, {
            projectId,
            raw: true,
        })
            .then((blob) => readBlobBuffer(blob))
            .then((buffer) => new FontFace("GlyphlabPreview", buffer).load())
            .then((loaded) => {
                if (disposed) return;
                face = loaded;
                document.fonts.add(loaded);
                installed = true;
                setState({ loading: false, ready: true });
            })
            .catch(() => {
                if (!disposed)
                    setState({ loading: false, ready: false, error: "load" });
            });
        return () => {
            disposed = true;
            if (installed && face) document.fonts.delete(face);
        };
    }, [artifact, projectId]);
    return state;
}
