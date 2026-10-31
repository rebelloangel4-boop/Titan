"""Bounded local deliverable workflows. No network, arbitrary shell or financial orders."""
import csv,io,json,math,shutil,subprocess,tempfile,wave,struct
from pathlib import Path
from .workspace import Workspace

def backtest(payload):
 prices=payload.get('prices');window=payload.get('window',3);fee=payload.get('fee_bps',10);capital=payload.get('capital',100000)
 if not isinstance(prices,list) or not 4<=len(prices)<=100000 or any(isinstance(v,bool) or not isinstance(v,(float,int)) or not math.isfinite(v) or not 0<v<1e10 for v in prices):raise ValueError('Provide 4–100000 finite positive closing prices')
 if isinstance(window,bool) or not isinstance(window,int) or not 2<=window<len(prices):raise ValueError('Invalid moving-average window')
 for v in (fee,capital):
  if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v):raise ValueError('Invalid cost/capital')
 if not 0<=fee<=1000 or not 0<capital<=1e10:raise ValueError('Invalid cost/capital range')
 equity=float(capital);peak=equity;drawdown=0.;held=0;trades=0;curve=[]
 # Signal uses only closes ending at i-1. Position earns return from i-1 to i.
 for i in range(window,len(prices)):
  signal=int(prices[i-1]>sum(prices[i-window:i])/window)
  turnover=abs(signal-held);equity*=1-turnover*fee/10000
  if turnover:trades+=1
  equity*=1+signal*(prices[i]/prices[i-1]-1);held=signal;peak=max(peak,equity);drawdown=max(drawdown,1-equity/peak)
  if (i-window)%max(1,math.ceil((len(prices)-window)/1000))==0 or i==len(prices)-1:curve.append({'bar':i,'position':held,'equity':round(equity,6)})
 if held:equity*=1-fee/10000;trades+=1
 return {'initial_capital':capital,'final_equity':equity,'return_pct':100*(equity/capital-1),'max_drawdown_pct':100*max(drawdown,1-equity/peak),'trades':trades,'curve':curve,'verification':'deterministic_historical_paper_simulation','limitations':['User-supplied closing prices; not verified market data','No live orders, taxes, liquidity, corporate actions or intrabar fills','Long-only unit exposure; no leverage; no prediction of future returns']}

def document(db,job,payload):
 title=payload.get('title',job['objective']);text=payload.get('text','')
 if not isinstance(title,str) or not isinstance(text,str) or len(title)>200 or len(text)>200000:raise ValueError('Document too large')
 from .security import redact
 content=redact('# '+title+'\n\n'+text+'\n').encode()
 return Workspace(db).artifact(job.get('project') or 'default',job['id'],'report.md',content,'text/markdown')

def video(db,job,payload):
 """Produces a real animated title-card MP4 with synthetic tone audio; never claims AI voice."""
 if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):raise RuntimeError('FFmpeg and ffprobe required')
 title=payload.get('title','TITAN local rendering');seconds=payload.get('seconds',3)
 if not isinstance(title,str) or len(title)>120 or isinstance(seconds,bool) or not isinstance(seconds,int) or not 1<=seconds<=15:raise ValueError('Title max 120 chars; duration 1–15 seconds')
 # Write text as PPM pixels using a tiny bundled bitmap alphabet, avoiding filter injection/fonts.
 from .raster import title_frame
 with tempfile.TemporaryDirectory() as d:
  d=Path(d);image=d/'title.ppm';image.write_bytes(title_frame(title,360,640));audio=d/'tone.wav'
  with wave.open(str(audio),'wb') as w:
   w.setnchannels(1);w.setsampwidth(2);w.setframerate(22050)
   w.writeframes(b''.join(struct.pack('<h',int(1000*math.sin(2*math.pi*220*i/22050)*min(1,i/2205,(seconds*22050-i)/2205))) for i in range(seconds*22050)))
  output=d/'video.mp4'
  cmd=['ffmpeg','-nostdin','-v','error','-threads','1','-loop','1','-i',str(image),'-i',str(audio),'-vf',"zoompan=z='min(zoom+0.0005,1.06)':d=1:s=360x640:fps=24",'-t',str(seconds),'-c:v','libx264','-preset','ultrafast','-threads','1','-pix_fmt','yuv420p','-c:a','aac','-movflags','+faststart','-y',str(output)]
  subprocess.run(cmd,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=45)
  probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(output)],timeout=10))
  if not any(s['codec_type']=='video' for s in probe['streams']) or not any(s['codec_type']=='audio' for s in probe['streams']):raise RuntimeError('Rendered media missing a stream')
  artifact=Workspace(db).artifact(job.get('project') or 'default',job['id'],'titan-preview.mp4',output.read_bytes(),'video/mp4')
  return {**artifact,'duration':float(probe['format']['duration']),'width':360,'height':640,'verification':'ffprobe_audio_video_streams','style':'Animated title card with synthetic tone; no natural voice or character animation'}

def run(db,job,kind,payload):
 if kind=='document':return document(db,job,payload)
 if kind=='video':return video(db,job,payload)
 if kind=='backtest':
  result=backtest(payload);a=Workspace(db).artifact(job.get('project') or 'default',job['id'],'paper-backtest.json',json.dumps(result,indent=2,allow_nan=False).encode(),'application/json')
  return {**result,'artifact':a}
 raise ValueError('Unsupported local domain workflow')
