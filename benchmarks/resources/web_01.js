function cfpParam(name) {
    var regex = new RegExp("[#]" + name + "=([^\\?&#]*)");
    var t = window.location.href;
    var loc=t.replace(/%23/g,"#");
    var results = regex.exec(loc);
    return (results === null) ? "" : unescape( results[1] );
}

function cfpMatchDef(val,regex,def) {
    var results = regex.exec(val);
    return (results === null) ? def : val;
}

function cfpAlphaParam(name,def) {
    var regex = new RegExp("^[a-zA-Z0-9.!?; \t_]+$");
    return cfpMatchDef(cfpParam(name),regex,def);
}

var cfpPid= cfpAlphaParam("pid",0);
var cfpPrBase="https://www.bugbountyhunter.com/";
var cfpClick = cfpParam("clk");
var cfpOrd = cfpParam("n");

if(cfpOrd === ""){
    var axel = Math.random() + "";
    cfpOrd = axel * 1000000000000000000;
}

function pr_swfver(){
    var osf,osfd,i,axo=1,v=0,nv=navigator;
    if(nv.plugins&&nv.mimeTypes.length){
        osf=nv.plugins["Shockwave Flash"];
        if(osf&&osf.description){
            osfd=osf.description;
            v=parseInt(osfd.substring(osfd.indexOf(".")-2))
        }
    }
    else{
        try{
            for(i=5;axo!=null;i++){
                axo=new ActiveXObject("ShockwaveFlash.ShockwaveFlash."+i);v=i
            }
        }catch(e){}
    }
    return v;
}

var pr_d=new Date();pr_d=pr_d.getDay()+"|"+pr_d.getHours()+":"+pr_d.getMinutes()+"|"+-pr_d.getTimezoneOffset()/60;
var pr_redir=cfpClick+"$CTURL$";
var pr_nua=navigator.userAgent.toLowerCase();
var pr_sec=((document.location.protocol=='https:')?'&secure=1':'');
var pr_pos="",pr_inif=(window!=top);

if(pr_inif){
    try{
        pr_pos=(typeof(parent.document)!="unknown")?(((typeof(inDapIF)!="undefined")&&(inDapIF))||(parent.document.domain==document.domain))?"&pos=s":"&pos=x":"&pos=x";
    }
    catch(e){
        pr_pos="&pos=x";
    }
    if(pr_pos=="&pos=x"){
        var pr_u=new RegExp("[A-Za-z]+:[/][/][A-Za-z0-9.-]+");
        var pr_t=this.window.document.referrer;
        var pr_m=pr_t.match(pr_u);
        if(pr_m!=null){
            pr_pos+="&dom="+pr_m[0];
        }
    }
    else{
        if(((typeof(inDapMgrIf)!="undefined")&&(inDapMgrIf))||((typeof(isAJAX)!="undefined")&&(isAJAX))){
            pr_pos+="&ajx=1"
        }
    }
}
var pr_s=document.location.protocol+"//"+cfpPrBase+"&flash="+pr_swfver()+"&time="+pr_d+"&redir="+pr_redir+pr_pos+pr_sec+"&r="+cfpOrd;
document.write("<script src='"+pr_s+"'><\/script>");
