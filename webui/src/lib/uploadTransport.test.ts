import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { uploadWithProgress } from "./api";
import { saveToken } from "./token";
class FakeXHR {
 static latest:FakeXHR;
 constructor(){FakeXHR.latest=this;}
 status=200;responseText='{"job_id":"job"}';headers=new Map<string,string>();
 upload={onprogress:undefined as undefined|((event:{lengthComputable:boolean;loaded:number;total:number})=>void)};
 onload?:()=>void;onerror?:()=>void;onabort?:()=>void;onloadend?:()=>void;
 open=vi.fn();send=vi.fn();abort=vi.fn(()=>{this.onabort?.();this.onloadend?.();});
 getResponseHeader=()=>null;
 setRequestHeader=(key:string,value:string)=>this.headers.set(key,value);
}
beforeEach(()=>{vi.stubGlobal("XMLHttpRequest",FakeXHR);localStorage.clear();});afterEach(()=>vi.unstubAllGlobals());
it("reports computable progress and authenticates XHR without query credentials",async()=>{
 const token=`glp_${"a".repeat(43)}`;saveToken("p",token);const progress=vi.fn();const promise=uploadWithProgress("/projects/p/uploads","p",new File(["abc"],"file"),progress);
 const xhr=FakeXHR.latest;expect(xhr.open).toHaveBeenCalledWith("POST","http://localhost/api/projects/p/uploads");expect(xhr.headers.get("authorization")).toBe(`Bearer ${token}`);
 xhr.upload.onprogress?.({lengthComputable:true,loaded:2,total:8});expect(progress).toHaveBeenCalledWith(25);xhr.onload?.();xhr.onloadend?.();await expect(promise).resolves.toEqual({job_id:"job"});
});
it.each([[429,"E_RATE_LIMITED"],[409,"E_QUOTA_EXCEEDED"]])("normalizes XHR status %i",async(status,code)=>{
 const promise=uploadWithProgress("/upload","p",new File([],"x"),()=>undefined);const xhr=FakeXHR.latest;xhr.status=status;xhr.responseText=JSON.stringify({error:{code,message:"later",detail:{retry_after:1}}});xhr.onload?.();await expect(promise).rejects.toMatchObject({status,code,detail:{retry_after:1}});
});
it("abort rejects and releases its listener",async()=>{
 const controller=new AbortController();const remove=vi.spyOn(controller.signal,"removeEventListener");const promise=uploadWithProgress("/upload","p",new File([],"x"),()=>undefined,controller.signal);controller.abort();await expect(promise).rejects.toMatchObject({name:"AbortError"});expect(FakeXHR.latest.abort).toHaveBeenCalledOnce();expect(remove).toHaveBeenCalledWith("abort",expect.any(Function));
});
it("malformed successful responses fail visibly",async()=>{const promise=uploadWithProgress("/upload","p",new File([],"x"),()=>undefined);FakeXHR.latest.responseText="bad";FakeXHR.latest.onload?.();await expect(promise).rejects.toMatchObject({code:"E_INTERNAL",status:200});});
