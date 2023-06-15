import os
from pprint import pprint
import sys

# from zmq import has
from solver import SolverMain
import numpy as np
import AST
import math
import shutil
import Constraints

def genFixedPoint(num) -> str:
    """ 
    This compiler uses a 8Q8 format for fixed point representation
    8 mantissa bits + 8 fraction fits => we have 16 bits for every colour value
    """
    # print(num)
    # print(type(num))
    # exit()
    num*=2**8
    # print(num)
    # exit()
    num=int(num)
    if num<0:
        num+=2**16
    return '{:016b}'.format(num)

def calcLines(stencil:dict,hasLineBuffer:dict,readRegs:dict,combine:bool=False):
    # print("calc Lines initial")
    # pprint(hasLineBuffer)
    for producer in hasLineBuffer.keys():
        # print(f"Producer {producer}")
        toAdd=0
        for consumer in stencil[producer].keys():
            sh = stencil[producer][consumer][1]
            if producer in readRegs.keys():
                if consumer in readRegs[producer].keys():
                    continue
            if sh>1:
                if sh%2==0:
                    toAdd+=int(sh/2)
                else:
                    toAdd+=int((sh-1)/2)
        # print(f"Consumer {consumer} to add {toAdd}")
        if combine:
            hasLineBuffer[producer]+=math.ceil(toAdd/2)
        else:
            hasLineBuffer[producer]+=toAdd

def augmentLevels(hasLB:dict,accessLevels:dict,dependency:dict):
	for stage in hasLB.keys():
		if stage not in accessLevels.keys():
			accessLevels[stage] = {}
			accessLevels[stage] = Constraints.genLevel(dependency,stage)

def hasLB(stencil:dict,newSCS:dict,readRegs:dict,width:int,threshold:int=50,combine:bool=False):
    hasLineBuffer={}
    hasFIFO={}
    # print("Has LB started")
    if combine:
        width*=2
    # print(f"Width is {width}")
    for producer in stencil.keys():
        maxdiff = 0
        for consumer in stencil[producer].keys():
            # print(f"Producer: {producer}, Consumer: {consumer}")
            if newSCS[consumer]-newSCS[producer]>maxdiff:
                # print(f"SCP {newSCS[producer]}, SCC {newSCS[consumer]}")
                maxdiff=newSCS[consumer]-newSCS[producer]-1
        if maxdiff>threshold:
            # print(f"Maxdiff {maxdiff}, Width {width}")
            hasLineBuffer[producer] = math.ceil(maxdiff/width)
            if(maxdiff%width==0):
                hasLineBuffer[producer] += 1
        else:
            hasFIFO[producer]=int(maxdiff)+1
    calcLines(stencil,hasLineBuffer,readRegs,combine)
    print('====================hasLB=====================')
    print(hasLineBuffer)
    return hasLineBuffer,hasFIFO


def cleanDag(dependency,readRegs,commonShiftReg):
    dag={}
    for producer in dependency.keys():
        dag[producer]=[]
        toRemove=[]
        if producer in readRegs.keys():
            for consumer in readRegs[producer].keys():
                toRemove=list(np.unique(toRemove+readRegs[producer][consumer]))
        if producer in commonShiftReg.keys():
            for consumer in commonShiftReg[producer].keys():
                toRemove=list(np.unique(toRemove+commonShiftReg[producer][consumer]))
        for consumer in dependency[producer].keys():
            if consumer in toRemove:
                continue
            dag[producer].append(consumer)
    return dag


class schedule:
    def __init__(self,width,sram,Ifile,OPath,combine) -> None:
        self.width = width
        self.sram = sram
        self.Ifile = Ifile
        self.OPath = OPath
        self.combine = combine
        # if self.width<1000:
        #     self.combine = combine
        self.dependency,self.stencils,self.scs,self.readRegs,self.pad,self.newSCS,self.accessLevels,self.virtStage=SolverMain(Ifile,width,sram,self.combine)
        self.hasLineBuffer,self.hasFIFO = hasLB(self.stencils,self.newSCS,self.readRegs,width,combine=combine)
        augmentLevels(self.hasLineBuffer,self.accessLevels,self.dependency)
        self.parameters={}
        self.wires={}
    
    def genRAMcontroller(self):
        path=os.path.join(self.OPath,"sram_controllers.sv")
        modFile=open(path,'a')
        ramControllerWires={}
        ramControllerParam={}
        redirectionWires={}
        addrGenerators={}
        for producer in self.hasLineBuffer.keys():
            lines=self.hasLineBuffer[producer]
            oldProducer = producer
            if producer[:-2] in self.virtStage.keys():
                producer = producer[:-2]
            # print(f"Producer {producer} oldProducer {oldProducer}")
            params=""
            curModule=f"sram_con_{producer}"
            if curModule in ramControllerWires.keys():
                continue
            ramControllerWires[curModule]=[]
            # print(f"LBController for {producer}")
            addrGenerators[f"addr_gen_{producer}"]="LBController #(\n"
            modFile.write(f"module sram_con_{producer}\n")
            modFile.write("#(\n")
            modFile.write(f"\tparameter PORTS = {self.sram},\n")
            params+=f"\t.PORTS ({self.sram}),\n"
            if self.combine:
                modFile.write(f"\tparameter WIDTH = {2*self.width},\n")
                params+=f"\t.WIDTH ({2*self.width}),\n"
                modFile.write(f"\tparameter AW = {math.ceil(math.log2(2*self.width))},\n")
                params+="\t.AW (AW),\n"
                self.parameters["AW"] = math.ceil(math.log2(2*self.width))
            else:
                modFile.write(f"\tparameter WIDTH = {self.width},\n")
                params+=f"\t.WIDTH ({self.width}),\n"
                modFile.write(f"\tparameter AW = {math.ceil(math.log2(self.width))},\n")
                params+="\t.AW (AW),\n"
                self.parameters["AW"] = math.ceil(math.log2(self.width))
            modFile.write(f"\tparameter LINES_{producer} = {lines},\n")
            self.parameters[f"LINES_{producer}"] = lines
            params+=f"\t.LINES ({lines}),\n"
            modFile.write(f"\tparameter LINE_BITS_{producer} = {math.ceil(math.log2(lines))},\n")
            self.parameters[f"LINE_BITS_{producer}"] = math.ceil(math.log2(lines))
            params+=f"\t.LINE_BITS ({math.ceil(math.log2(lines))}),\n"
            modFile.write("\tparameter CHAN = 3,\n")
            modFile.write("\tparameter BITS = 16,\n")
            modFile.write(f"\tparameter ACC = {len(list(self.dependency[oldProducer].keys()))+1}")
            firstParam=True
            for consumer in self.dependency[oldProducer].keys():
                if oldProducer in self.readRegs.keys():
                    if consumer in self.readRegs[oldProducer].keys():
                        continue
                if(firstParam==True):
                    modFile.write(",\n")
                else:
                    firstParam=False
                addrGenerators[f"addr_gen_{producer}_{consumer}"]="LBController #(\n"
                addrGenerators[f"addr_gen_{producer}_{consumer}"]+=params
                if consumer[:-2] in self.virtStage.keys():
                    if consumer==self.virtStage[consumer[:-2]][1]:
                        addrGenerators[f"addr_gen_{producer}_{consumer}"]+=f"\t.OFFSET ({self.width}),\n"
                modFile.write(f"\tparameter SH_{producer}_{consumer} = {self.stencils[oldProducer][consumer][1]},\n")
                addrGenerators[f"addr_gen_{producer}_{consumer}"]+=f"\t.SH ({self.stencils[oldProducer][consumer][1]}),\n"
                self.parameters[f"SH_{producer}_{consumer}"] = self.stencils[oldProducer][consumer][1]
                if consumer[:-2] in self.virtStage.keys():
                    if f"SH_{producer}_{consumer[:-2]}" not in self.parameters.keys():
                        sh = self.stencils[oldProducer][self.virtStage[consumer[:-2]][0]][1] + self.stencils[oldProducer][self.virtStage[consumer[:-2]][1]][1]
                        modFile.write(f"\tparameter SH_{producer}_{consumer[:-2]} = {sh},\n")
                        self.parameters[f"SH_{producer}_{consumer[:-2]}"] = sh
                modFile.write(f"\tparameter SW_{producer}_{consumer} = {self.stencils[oldProducer][consumer][0]},\n")
                addrGenerators[f"addr_gen_{producer}_{consumer}"]+=f"\t.SW ({self.stencils[oldProducer][consumer][0]}),\n"
                self.parameters[f"SW_{producer}_{consumer}"] = self.stencils[oldProducer][consumer][0]
                modFile.write(f"\tparameter PAD_TOP_{producer}_{consumer} = {self.pad[oldProducer][consumer][0]}")
                self.parameters[f"PAD_TOP_{producer}_{consumer}"]=self.pad[oldProducer][consumer][0]
                addrGenerators[f"addr_gen_{producer}_{consumer}"]+=f"\t.PAD_TOP ({self.pad[oldProducer][consumer][0]}),\n"
                addrGenerators[f"addr_gen_{producer}_{consumer}"]+=f"\t.PAD_LEFT ({self.pad[oldProducer][consumer][2]}),\n"
                addrGenerators[f"addr_gen_{producer}_{consumer}"]+=f"\t.PAD_RIGHT ({self.pad[oldProducer][consumer][3]})\n"
                addrGenerators[f"addr_gen_{producer}_{consumer}"]+=f")\naddr_gen_{producer}_{consumer}\n("
            modFile.write(",\n")
            modFile.write(f"\tparameter SH_{producer} = 1,\n")
            addrGenerators[f"addr_gen_{producer}"]+=params
            addrGenerators[f"addr_gen_{producer}"]+=f"\t.SH (1),\n"
            modFile.write(f"\tparameter SW_{producer}_{producer} = 1\n")
            addrGenerators[f"addr_gen_{producer}"]+=f"\t.SW (1),\n"
            addrGenerators[f"addr_gen_{producer}"]+=f"\t.PAD_TOP (0),\n"
            addrGenerators[f"addr_gen_{producer}"]+=f"\t.PAD_LEFT (0),\n"
            addrGenerators[f"addr_gen_{producer}"]+=f"\t.PAD_RIGHT (0)\n"
            addrGenerators[f"addr_gen_{producer}"]+=f")\naddr_gen_{producer}\n(\n"
            modFile.write(")\n(\n")

            """ 
            * We now generate the ports
            """
            modFile.write("\tinput logic clk,\n")
            ramControllerWires[curModule].append("clk")
            modFile.write("\tinput logic rstn,\n")
            ramControllerWires[curModule].append("rstn")
            addrGenerators[f"addr_gen_{producer}"]+="\t.clk (clk),\n"    
            addrGenerators[f"addr_gen_{producer}"]+="\t.start (rstn),\n"
            addrGenerators[f"addr_gen_{producer}"]+=f"\t.valid (write_enabled_{producer}),\n"
            modFile.write(f"\tinput logic write_enabled_{producer},\n")
            ramControllerWires[curModule].append(f"write_enabled_{producer}")
            # self.wires[f"write_enabled_{producer}"] = ("","")
            addrGenerators[f"addr_gen_{producer}"]+=f"\t.rowComplete(row_complete_{producer}),\n"
            self.wires[f"row_complete_{producer}"]=("","")
            for consumer in self.dependency[oldProducer].keys():  
                if oldProducer in self.readRegs.keys():
                    if consumer in self.readRegs[oldProducer].keys():
                        continue
                # addrGenerators[f"addr_gen_{producer}_{consumer}"]+="\t.clk (clk),\n"    
                # addrGenerators[f"addr_gen_{producer}_{consumer}"]+="\t.start (rstn),\n"
                # addrGenerators[f"addr_gen_{producer}_{consumer}"]+=f"\t.valid (read_enabled_{producer}_{consumer}),\n"
                modFile.write(f"\tinput logic read_enabled_{producer}_{consumer},\n")
                ramControllerWires[curModule].append(f"read_enabled_{producer}_{consumer}")
                # self.wires[f"read_enabled_{producer}_{consumer}"] = ("","")
                modFile.write(f"\tinput logic [AW-1:0] addrY_{producer}_{consumer},\n")
                ramControllerWires[curModule].append(f"addrY_{producer}_{consumer}")
                self.wires[f"addrY_{producer}_{consumer}"] = ("[AW-1:0]","")
                addrGenerators[f"addr_gen_{producer}_{consumer}"]+=f"\t.addrY (addrY_{producer}_{consumer}),\n"
                modFile.write(f"\tinput logic [LINE_BITS_{producer}-1:0] addrX_{producer}_{consumer} [SH_{producer}_{consumer}-1:0],\n")  
                ramControllerWires[curModule].append(f"addrX_{producer}_{consumer}")
                self.wires[f"addrX_{producer}_{consumer}"] = (f"[LINE_BITS_{producer}-1:0]",f"[SH_{producer}_{consumer}-1:0]")
                addrGenerators[f"addr_gen_{producer}_{consumer}"]+=f"\t.addrX (addrX_{producer}_{consumer}),\n"
                if consumer[:-2] in self.virtStage.keys():
                    if f"lb_to_sreg_{producer}_{consumer[:-2]}" not in self.wires.keys():
                        modFile.write(f"\toutput logic [CHAN-1:0][BITS-1:0] lb_to_sreg_{producer}_{consumer[:-2]} [SH_{producer}_{consumer[:-2]}-1:0],\n")
                        ramControllerWires[curModule].append(f"lb_to_sreg_{producer}_{consumer[:-2]}")
                        self.wires[f"lb_to_sreg_{producer}_{consumer[:-2]}"] = ("[CHAN-1:0][BITS-1:0]",f"[SH_{producer}_{consumer[:-2]}-1:0]")
                else:
                    modFile.write(f"\toutput logic [CHAN-1:0][BITS-1:0] lb_to_sreg_{producer}_{consumer} [SH_{producer}_{consumer}-1:0],\n")
                    ramControllerWires[curModule].append(f"lb_to_sreg_{producer}_{consumer}")
                    self.wires[f"lb_to_sreg_{producer}_{consumer}"] = ("[CHAN-1:0][BITS-1:0]",f"[SH_{producer}_{consumer}-1:0]")
                if self.pad[oldProducer][consumer][0]>0:
                    modFile.write(f"\tinput logic [PAD_TOP_{producer}_{consumer}:0] topPadMask_{producer}_{consumer},\n")
                    self.wires[f"topPadMask_{producer}_{consumer}"]=(f"[PAD_TOP_{producer}_{consumer}:0]","")
                    addrGenerators[f"addr_gen_{producer}_{consumer}"]+=f"\t.topPadMask (topPadMask_{producer}_{consumer}),\n"
                    ramControllerWires[curModule].append(f"topPadMask_{producer}_{consumer}")
                if self.pad[oldProducer][consumer][2]>0:
                    print(f"producer: {producer} consumer {consumer} leftPad {self.pad[oldProducer][consumer][2]}")
                    if consumer[-2:]=="_1" or consumer[-2:]=="_2":
                        if consumer==self.virtStage[consumer[:-2]][0]:
                            pass
                        else:
                            addrGenerators[f"addr_gen_{producer}_{consumer}"]+=f"\t.leftPadMask (leftPadMask_{producer}_{consumer[:-2]}),\n"
                    else:
                        addrGenerators[f"addr_gen_{producer}_{consumer}"]+=f"\t.leftPadMask (leftPadMask_{producer}_{consumer}),\n"
                if self.pad[oldProducer][consumer][3]>0:
                    print(f"producer: {producer} consumer {consumer} rightPad {self.pad[oldProducer][consumer][3]}")
                    if consumer[-2:]=="_1" or consumer[-2:]=="_2":
                        if consumer==self.virtStage[consumer[:-2]][0]:
                            pass
                        else:
                            addrGenerators[f"addr_gen_{producer}_{consumer}"]+=f"\t.rightPadMask (rightPadMask_{producer}_{consumer[:-2]}),\n"
                    else:
                        addrGenerators[f"addr_gen_{producer}_{consumer}"]+=f"\t.rightPadMask (rightPadMask_{producer}_{consumer}),\n"
                if consumer[-2:]=="_1" or consumer[-2:]=="_2":
                    if consumer==self.virtStage[consumer[:-2]][0]:
                        pass
                    else:
                        addrGenerators[f"addr_gen_{producer}_{consumer}"]+=f"\t.rowComplete(row_complete_{producer}_{consumer[:-2]}),\n"
                        self.wires[f"row_complete_{producer}_{consumer[:-2]}"]=("","")
                else:
                    addrGenerators[f"addr_gen_{producer}_{consumer}"]+=f"\t.rowComplete(row_complete_{producer}_{consumer}),\n"
                    self.wires[f"row_complete_{producer}_{consumer}"]=("","")
                addrGenerators[f"addr_gen_{producer}_{consumer}"]+="\t.clk (clk),\n"    
                addrGenerators[f"addr_gen_{producer}_{consumer}"]+="\t.start (rstn),\n"
                addrGenerators[f"addr_gen_{producer}_{consumer}"]+=f"\t.valid (read_enabled_{producer}_{consumer})\n"
                addrGenerators[f"addr_gen_{producer}_{consumer}"]+=");\n\n"
            modFile.write(f"\tinput logic [AW-1:0] addrY_{producer},\n")
            ramControllerWires[curModule].append(f"addrY_{producer}")
            addrGenerators[f"addr_gen_{producer}"]+=f"\t.addrY (addrY_{producer}),\n"
            self.wires[f"addrY_{producer}"] = ("[AW-1:0]","")
            modFile.write(f"\tinput logic [LINE_BITS_{producer}-1:0] addrX_{producer} [0:0],\n")  
            ramControllerWires[curModule].append(f"addrX_{producer}")
            addrGenerators[f"addr_gen_{producer}"]+=f"\t.addrX (addrX_{producer})\n"
            addrGenerators[f"addr_gen_{producer}"]+=");\n\n"
            self.wires[f"addrX_{producer}"] = (f"[LINE_BITS_{producer}-1:0]","[0:0]")
            modFile.write(f"\tinput logic [CHAN-1:0][BITS-1:0] comp_to_lb_{producer}\n")
            ramControllerWires[curModule].append(f"comp_to_lb_{producer}")
            if producer not in AST.inputStages:
                self.wires[f"comp_to_lb_{producer}"] = ("[CHAN-1:0][BITS-1:0]","")
            modFile.write(");\n")
            """ 
            * I will now genreate rest of the logic starting with 
            """
            portNum={}
            portNum[producer]=0
            levels = self.accessLevels[oldProducer]  #! could cause error
            port=0
            for lvl in levels.keys():
                if lvl == 0:
                    continue
                for accessor in levels[lvl]:
                # accessor = levels[lvl][0]
                    port+=1
                    if port==self.sram:
                        port=0
                    portNum[accessor]=port
            print(levels,portNum)
            modFile.write(f"logic [CHAN-1:0][BITS-1:0] Odata [LINES_{producer}-1:0][PORTS-1:0];\n")
            # modFile.write(f"logic [PORTS-1:0] port_count_ip [LINES_{producer}-1:0];\n")
            # modFile.write(f"logic [PORTS-1:0] port_count_op [LINES_{producer}-1:0];\n")
            modFile.write(f"bit [PORTS-1:0] ren [LINES_{producer}-1:0];\n")
            modFile.write(f"bit [PORTS-1:0] wen [LINES_{producer}-1:0];\n")
            modFile.write(f"logic [PORTS-1:0][AW-1:0] addr [LINES_{producer}-1:0];\n")
            modFile.write("genvar i,j;\n")
            modFile.write("integer lineNumIp;\n")
            modFile.write("integer lineNumOp;\n")
            # modFile.write("integer portNumIp;\n\n")
            # modFile.write("integer portNumOp;\n\n")
            modFile.write("always_comb begin\n")
            # modFile.write("\tport_count_ip = '{default:'0};\n")
            modFile.write("\tren = '{default:'0};\n")
            modFile.write("\twen = '{default:'0};\n")
            modFile.write("\taddr = '{default:'0};\n")
            modFile.write(f"\tif(write_enabled_{producer}==1) begin\n")
            modFile.write(f"\t\tlineNumIp = addrX_{producer}[0];\n")
            modFile.write(f"\t\taddr[lineNumIp][{portNum[producer]}] = addrY_{producer};\n")
            modFile.write(f"\t\twen[lineNumIp][{portNum[producer]}] = 'b1;\n")
            modFile.write("\tend\n")
            for consumer in self.dependency[oldProducer].keys(): 
                if oldProducer in self.readRegs.keys():
                    if consumer in self.readRegs[oldProducer].keys():
                        continue
                modFile.write(f"\tif(read_enabled_{producer}_{consumer}) begin\n")
                for i in range(self.stencils[oldProducer][consumer][1]):
                    if i<self.pad[oldProducer][consumer][0]:
                        modFile.write(f"\t\tif({i}<topPadMask_{producer}_{consumer}) begin\n")
                        modFile.write("\n")
                        modFile.write("\t\tend\n")
                        modFile.write(f"\t\telse begin\n")
                        modFile.write(f"\t\t\tlineNumIp = addrX_{producer}_{consumer}[{i}];\n")
                        modFile.write(f"\t\t\taddr[lineNumIp][{portNum[consumer]}] = addrY_{producer}_{consumer};\n")
                        modFile.write(f"\t\t\tren[lineNumIp][{portNum[consumer]}] = 'b1;\n")
                        modFile.write("\t\tend\n")
                        continue
                    modFile.write(f"\t\tlineNumIp = addrX_{producer}_{consumer}[{i}];\n")
                    # modFile.write("\tport_count_ip[lineNumIp] = port_count_ip[lineNumIp]+1;\n")
                    modFile.write(f"\t\taddr[lineNumIp][{portNum[consumer]}] = addrY_{producer}_{consumer};\n")
                    modFile.write(f"\t\tren[lineNumIp][{portNum[consumer]}] = 'b1;\n")
                modFile.write("\tend\n")
            modFile.write("end\n\n")
            modFile.write(f"sram\n#(\n")
            modFile.write(f"\t.LINES(LINES_{producer}),\n")
            modFile.write(f"\t.WIDTH(WIDTH),\n")
            modFile.write(f"\t.PORTS(PORTS)\n")
            modFile.write(f")\nsram_{producer}_inst\n(\n")
            modFile.write("\t.clk (clk),\n")
            modFile.write("\t.rstn (rstn),\n")
            modFile.write("\t.addr (addr),\n")
            modFile.write("\t.ren (ren),\n")
            modFile.write("\t.wen (wen),\n")
            modFile.write(f"\t.Idata (comp_to_lb_{producer}),\n")
            modFile.write("\t.Odata (Odata)\n);\n\n")  

            """ 
            * We now redirect the data to correct addresses.
            """
            modFile.write("always_comb begin\n")
            # modFile.write("\tport_count_op = '{default:'0};\n")
            # modFile.write(f"\tlineNumOp = addrX_{producer}[0];\n")
            # modFile.write("\tportNumOp = port_count_op[lineNumOp];\n")
            # modFile.write("\tport_count_op[lineNumOp] = port_count_op[lineNumOp]+1;\n")
            for consumer in self.dependency[oldProducer].keys():
                if oldProducer in self.readRegs.keys():
                    if consumer in self.readRegs[oldProducer].keys():
                        continue
                modFile.write(f"\tif(read_enabled_{producer}_{consumer}) begin\n")
                if consumer[:-2] in self.virtStage.keys():
                    if consumer[-1] == "1":
                        for i in range(self.stencils[oldProducer][consumer][1]): #TODO Complete this and codeGen should be ready
                            modFile.write(f"\t\tlineNumOp = addrX_{producer}_{consumer}[{i}];\n")
                            if i<self.pad[oldProducer][consumer][0]:
                                modFile.write(f"\t\tlb_to_sreg_{producer}_{consumer[:-2]}[{2*i}] = ({i}<topPadMask_{producer}_{consumer})? 'b0 : Odata[lineNumOp][{portNum[consumer]}];\n")
                                continue
                            modFile.write(f"\t\tlb_to_sreg_{producer}_{consumer[:-2]}[{2*i}] = Odata[lineNumOp][{portNum[consumer]}];\n")
                    else:
                        for i in range(self.stencils[oldProducer][consumer][1]): #TODO Complete this and codeGen should be ready
                            modFile.write(f"\t\tlineNumOp = addrX_{producer}_{consumer}[{i}];\n")
                            if i<self.pad[oldProducer][consumer][0]:
                                modFile.write(f"\t\tlb_to_sreg_{producer}_{consumer[:-2]}[{2*i+1}] = ({i}<topPadMask_{producer}_{consumer})? 'b0 : Odata[lineNumOp][{portNum[consumer]}];\n")
                                continue
                            modFile.write(f"\t\tlb_to_sreg_{producer}_{consumer[:-2]}[{2*i+1}] = Odata[lineNumOp][{portNum[consumer]}];\n")
                else:
                    for i in range(self.stencils[oldProducer][consumer][1]):
                        modFile.write(f"\t\tlineNumOp = addrX_{producer}_{consumer}[{i}];\n")
                        # modFile.write("\tport_count_op[lineNumOp] = port_count_op[lineNumOp]+1;\n")
                        if i<self.pad[oldProducer][consumer][0]:
                            modFile.write(f"\t\tlb_to_sreg_{producer}_{consumer}[{i}] = ({i}<topPadMask_{producer}_{consumer})? 'b0 : Odata[lineNumOp][{portNum[consumer]}];\n")
                            continue
                        modFile.write(f"\t\tlb_to_sreg_{producer}_{consumer}[{i}] = Odata[lineNumOp][{portNum[consumer]}];\n")   
                modFile.write("\tend\n")   
                modFile.write("\telse begin\n")
                for i in range(self.stencils[oldProducer][consumer][1]):
                    if consumer[:-2] in self.virtStage.keys():
                        if consumer[-1]=='1':
                            modFile.write(f"\t\tlb_to_sreg_{producer}_{consumer[:-2]}[{2*i}] = 'b0;\n")
                        else:
                            modFile.write(f"\t\tlb_to_sreg_{producer}_{consumer[:-2]}[{2*i+1}] = 'b0;\n")
                    else:
                        modFile.write(f"\t\tlb_to_sreg_{producer}_{consumer}[{i}] = 'b0;\n")
                modFile.write("\tend\n")
            modFile.write("end\n")
            modFile.write("endmodule\n\n")
        modFile.close()
        return ramControllerWires,addrGenerators


    def genFIFO(self):
        path=os.path.join(self.OPath,"fifo.sv")
        modFile=open(path,'a')
        fifoMods={}
        for producer in self.hasFIFO.keys():
            oldProducer = producer
            if producer[:-2] in self.virtStage.keys():
                oldProducer = producer[:-2]
            module=f"fifo_{oldProducer}"
            if module in fifoMods.keys():
                continue
            modFile.write(f"module {module}\n")
            modFile.write("#(\n")
            modFile.write(f"\tparameter FIFO_SIZE_{oldProducer} = {self.hasFIFO[producer]},\n")
            self.parameters[f"FIFO_SIZE_{oldProducer}"]=self.hasFIFO[producer]
            fifoMods[module]=[]
            portString="\tinput logic clk,\n\tinput logic rstn,\n"
            fifoMods[module].append("clk")
            fifoMods[module].append("rstn")
            assignString=""
            for consumer in self.dependency[producer].keys():
                if oldProducer in self.readRegs.keys():
                    if consumer in self.readRegs[producer].keys():
                        continue
                oldConsumer = consumer
                if consumer[-2:]=="_1" or consumer[-2:]=="_2":
                    oldConsumer = consumer[:-2]
                if f"lb_to_sreg_{oldProducer}_{oldConsumer}" in self.wires.keys():
                    continue
                modFile.write(f"\tparameter INDEX_{oldConsumer} = {self.newSCS[consumer]-self.newSCS[producer]-2},\n")
                portString+=f"\toutput logic [CHAN-1:0][BITS-1:0] lb_to_sreg_{oldProducer}_{oldConsumer} [0:0],\n"
                fifoMods[module].append(f"lb_to_sreg_{oldProducer}_{oldConsumer}")
                self.wires[f"lb_to_sreg_{oldProducer}_{oldConsumer}"]=("[CHAN-1:0][BITS-1:0]","[0:0]")
                assignString+=f"assign lb_to_sreg_{oldProducer}_{oldConsumer}[0] = buffer[INDEX_{oldConsumer}];\n"
            modFile.write("\tparameter CHAN = 3,\n")
            modFile.write("\tparameter BITS = 16\n")
            modFile.write(")\n(\n")
            modFile.write(portString)
            modFile.write(f"\tinput logic [CHAN-1:0][BITS-1:0] comp_to_lb_{oldProducer}\n")
            fifoMods[module].append(f"comp_to_lb_{oldProducer}")
            if producer not in AST.inputStages:
                self.wires[f"comp_to_lb_{oldProducer}"]=("[CHAN-1:0][BITS-1:0]","")
            modFile.write(");\n\n")
            modFile.write(f"logic [CHAN-1:0][BITS-1:0] buffer [FIFO_SIZE_{oldProducer}-1:0];\n\n")
            modFile.write("always_ff @(posedge clk or negedge rstn) begin\n")
            modFile.write("\tif(!rstn) begin\n")
            for i in range(self.hasFIFO[producer]):
                modFile.write(f"\t\tbuffer[{i}]<=0;\n")
            modFile.write("\tend")
            modFile.write("\telse begin\n")
            for i in range(self.hasFIFO[producer]):
                if(i==0):
                    modFile.write(f"\t\tbuffer[{i}] <= comp_to_lb_{oldProducer};\n")
                    continue
                modFile.write(f"\t\tbuffer[{i}] <= buffer[{i-1}];\n")
            modFile.write("\tend\n")
            modFile.write("end\n\n")
            modFile.write(assignString)
            modFile.write("endmodule\n\n\n")
        modFile.close()
        return fifoMods

    # def combinationRedirection(self):
    #     for stage in self.virtStage.keys():
    #         shStage =    0

    def genShiftReg(self):
        path=os.path.join(self.OPath,"shift_regs.sv")
        modFile=open(path,'a')
        shiftMods={}
        for node in AST.head.keys():
            for producer in AST.head[node].producers:
                newProducer = producer
                if producer in self.virtStage.keys():
                    newProducer = self.virtStage[producer][0]
                if newProducer in self.readRegs.keys():
                    tNode = node
                    if node in self.virtStage.keys():
                        tNode = self.virtStage[node][0]
                    if tNode in self.readRegs[newProducer].keys():
                        continue
                module = f"shift_reg_{producer}_{node}"
                shiftMods[module]=[]
                modFile.write(f"module {module}\n")
                modFile.write("#(\n")
                if producer in self.virtStage.keys():
                    newProducer = self.virtStage[producer][0]
                if node in self.virtStage.keys():
                    sh = self.stencils[newProducer][self.virtStage[node][0]][1]+self.stencils[newProducer][self.virtStage[node][1]][1]
                    sw = self.stencils[newProducer][self.virtStage[node][0]][0]
                    pr = self.pad[newProducer][self.virtStage[node][0]][3]
                    pl = self.pad[newProducer][self.virtStage[node][0]][2]
                else:
                    sh = self.stencils[newProducer][node][1]
                    sw = self.stencils[newProducer][node][0]
                    pr = self.pad[newProducer][node][3]
                    pl = self.pad[newProducer][node][2]
                modFile.write(f"\tparameter SH_{producer}_{node} = {sh},\n")
                modFile.write(f"\tparameter SW_{producer}_{node} = {sw},\n")
                modFile.write(f"\tparameter PAD_RIGHT_{producer}_{node} = {pr},\n")
                self.parameters[f"PAD_RIGHT_{producer}_{node}"] = pr
                modFile.write(f"\tparameter PAD_LEFT_{producer}_{node} = {pl},\n")
                self.parameters[f"PAD_LEFT_{producer}_{node}"] = pl
                modFile.write(f"\tparameter CHAN = 3,\n")
                modFile.write(f"\tparameter BITS = 16\n")
                modFile.write(")\n(\n")
                modFile.write(f"\tinput logic clk,\n")
                shiftMods[module].append("clk")
                modFile.write(f"\tinput logic rstn,\n")
                shiftMods[module].append("rstn")
                modFile.write(f"\tinput logic read_enable_{module},\n")
                shiftMods[module].append(f"read_enable_{module}")
                self.wires[f"read_enable_{module}"] = ("","")
                modFile.write(f"\tinput logic row_complete_{producer}_{node},\n")
                shiftMods[module].append(f"row_complete_{producer}_{node}")
                self.wires[f"row_complete_{producer}_{node}"] = ("","")
                modFile.write(f"\tinput logic [CHAN-1:0][BITS-1:0] lb_to_sreg_{producer}_{node} [SH_{producer}_{node}-1:0],\n")
                shiftMods[module].append(f"lb_to_sreg_{producer}_{node}")
                if pl>0:
                    modFile.write(f"\tinput logic [PAD_LEFT_{producer}_{node}:0] leftPadMask_{producer}_{node},\n")
                    self.wires[f"leftPadMask_{producer}_{node}"] = (f"[PAD_LEFT_{producer}_{node}:0]","")
                    shiftMods[module].append(f"leftPadMask_{producer}_{node}")
                if pr>0:
                    modFile.write(f"\tinput logic [PAD_RIGHT_{producer}_{node}:0] rightPadMask_{producer}_{node},\n")
                    self.wires[f"rightPadMask_{producer}_{node}"] = (f"[PAD_RIGHT_{producer}_{node}:0]","")
                    shiftMods[module].append(f"rightPadMask_{producer}_{node}")
                isFirst=True
                alwaysWrite="always_ff @(posedge clk or negedge rstn) begin\n"
                # alwaysWrite="\tif(!rstn) begin\n"
                alwaysWriteRstn = "\tif(!rstn) begin\n"
                alwaysWriteRegular = "\telse begin\n"
                alwaysRead="always_ff @(posedge clk) begin\n"
                assignOP=""
                registers=""
                for i in range(sh):
                    for j in range(sw):
                        if(isFirst==False):
                            modFile.write(",\n")
                        modFile.write(f"\toutput logic [CHAN-1:0][BITS-1:0] sreg_to_comp_{producer}_{node}_{i+1}_{j+1}")
                        shiftMods[module].append(f"sreg_to_comp_{producer}_{node}_{i+1}_{j+1}")
                        self.wires[f"sreg_to_comp_{producer}_{node}_{i+1}_{j+1}"]=("[CHAN-1:0][BITS-1:0]","")
                        registers+=f"logic [CHAN-1:0][BITS-1:0] sreg_{i+1}_{j+1};\nlogic [CHAN-1:0][BITS-1:0] out_temp_{i+1}_{j+1};\n"
                        if j==0:
                            alwaysWriteRstn+=f"\t\tsreg_{i+1}_{j+1} <= 0;\n"
                            alwaysWriteRegular+=f"\t\tsreg_{i+1}_{j+1} <= lb_to_sreg_{producer}_{node}[{i}];\n"
                        else:
                            alwaysWriteRstn+=f"\t\tsreg_{i+1}_{j+1} <= 0;\n"
                            alwaysWriteRegular+=f"\t\tsreg_{i+1}_{j+1} <= sreg_{i+1}_{j};\n"
                        if pr>(sw-j-1):
                            alwaysRead+=f"\tif(rightPadMask_{producer}_{node}>{sw-j-1}) begin\n"
                            alwaysRead+=f"\t\tout_temp_{i+1}_{j+1} <= 0;\n"
                            alwaysRead+="\tend\n"
                            alwaysRead+=f"\telse begin\n"
                            alwaysRead+=f"\t\tout_temp_{i+1}_{j+1} <= sreg_{i+1}_{j+1};\n"
                            alwaysRead+="\tend\n"
                        else:
                            if pl>j:
                                alwaysRead+=f"\tif(leftPadMask_{producer}_{node}>{j} && rightPadMask_{producer}_{node}==0) begin\n"
                                alwaysRead+=f"\t\tout_temp_{i+1}_{j+1} <= 0;\n"
                                alwaysRead+="\tend\n"
                                alwaysRead+=f"\telse begin\n"
                                alwaysRead+=f"\t\tout_temp_{i+1}_{j+1} <= sreg_{i+1}_{j+1};\n"
                                alwaysRead+="\tend\n"
                            else:
                                alwaysRead+=f"\tout_temp_{i+1}_{j+1} <= sreg_{i+1}_{j+1};\n"
                        isFirst=False
                modFile.write("\n);\n\n")
                modFile.write(registers)
                alwaysWriteRegular+="\tend\n"
                alwaysWriteRstn+="\tend\n"
                alwaysWrite+=alwaysWriteRstn
                alwaysWrite+=alwaysWriteRegular
                alwaysRead+="end\n\n"
                alwaysWrite+="end\n\n"
                # todo Implement left and right pad masks for this. When implemented they will return 0 for the appropriate ports.
                alwaysPad="always_ff @(posedge clk) begin\n";
                modFile.write(alwaysWrite)
                modFile.write(alwaysRead)
                for i in range(sh):
                    for j in range(sw):
                        assignOP+=f"assign sreg_to_comp_{producer}_{node}_{i+1}_{j+1} = out_temp_{i+1}_{sw-j};\n"
                assignOP+="\n"
                modFile.write(assignOP)
                modFile.write("endmodule\n\n")
        modFile.close()
        return shiftMods


    def genCompute(self) -> dict:
        computeMods={}
        path=os.path.join(self.OPath,"compute_modules.sv")
        modFile=open(path,'a')
        # print("=============Generating compute modules=============")
        for node in AST.head.keys():
            # print(f"Current node {node}")
            coefs=""
            assignments=""
            assignmentsRed=""
            assignmentsGreen=""
            assignmentsBlue=""
            multRed=[]
            multGreen=[]
            multBlue=[]
            module=f"compute_{node}"
            computeMods[module]=[]
            modFile.write(f"module {module}\n")
            modFile.write("#(\n")
            modFile.write("\tparameter CHAN = 3,\n")
            modFile.write("\tparameter BITS = 16\n")
            modFile.write(")\n(\n")
            modFile.write("\tinput logic clk,\n")
            computeMods[module].append("clk")
            for producer in AST.head[node].producers:
                # print(f"\tCurrent Producer {producer}")
                newProducer = producer
                if producer in self.virtStage.keys():
                    newProducer = self.virtStage[producer][0]
                tNode = node
                if node in self.virtStage.keys():
                    tNode = self.virtStage[node][0]
                    sh = self.stencils[newProducer][self.virtStage[node][0]][1]+self.stencils[newProducer][self.virtStage[node][1]][1]
                    sw = self.stencils[newProducer][self.virtStage[node][0]][0]
                    pr = self.pad[newProducer][self.virtStage[node][0]][3]
                    pl = self.pad[newProducer][self.virtStage[node][0]][2]
                else:
                    sh = self.stencils[newProducer][node][1]
                    sw = self.stencils[newProducer][node][0]
                    pr = self.pad[newProducer][node][3]
                    pl = self.pad[newProducer][node][2]
                for xPos in AST.head[node].coefficient[producer].keys():
                    # print(f"\t\tX_pos is {xPos}")
                    for yPos in AST.head[node].coefficient[producer][xPos].keys():
                        # print(f"\t\t\tY_pos is {yPos}")
                        port = f"sreg_to_comp_{producer}_{node}_{yPos+math.ceil(sh/2)}_{xPos+math.ceil(sw/2)}"
                        if newProducer in self.readRegs.keys():
                            if tNode in self.readRegs[newProducer].keys():
                                source = self.readRegs[newProducer][tNode]
                                if source[-2:]=="_1" or source[-2:]=="_2":
                                    source = source[:-2]
                                port = f"sreg_to_comp_{producer}_{source}_{yPos+math.ceil(sh/2)}_{xPos+math.ceil(sw/2)}"                            
                        modFile.write(f"\tinput [CHAN-1:0][BITS-1:0] {port},\n")
                        computeMods[module].append(port)
                        coef=f"coef_{port}"
                        coefValRed=f"16'b{genFixedPoint(AST.head[node].coefficient[producer][xPos][yPos][0])}"
                        coefValGreen=f"16'b{genFixedPoint(AST.head[node].coefficient[producer][xPos][yPos][1])}"
                        coefValBlue=f"16'b{genFixedPoint(AST.head[node].coefficient[producer][xPos][yPos][2])}"
                        coefs+=f"logic signed [BITS-1:0]{coef}_red = {coefValRed};\n"
                        coefs+=f"logic signed [BITS-1:0]{coef}_green = {coefValGreen};\n"
                        coefs+=f"logic signed [BITS-1:0]{coef}_blue = {coefValBlue};\n"
                        assignments+=f"logic signed [BITS-1:0] red_{port};\n"
                        assignmentsRed+=f"\t\tred_{port} = {port}[0];\n"
                        assignments+=f"logic signed [BITS-1:0] green_{port};\n"
                        assignmentsGreen+=f"\t\tgreen_{port} = {port}[1];\n"
                        assignments+=f"logic signed [BITS-1:0] blue_{port};\n"
                        assignmentsBlue+=f"\t\tblue_{port} = {port}[2];\n"
                        multRed.append(f"{coef}_red * red_{port}")
                        multGreen.append(f"{coef}_green * green_{port}")
                        multBlue.append(f"{coef}_blue * blue_{port}")
            assignments+=f"logic signed [2*BITS-1:0] op_red;\n"
            assignments+=f"logic signed [2*BITS-1:0] op_green;\n"
            assignments+=f"logic signed [2*BITS-1:0] op_blue;\n"
            alwaysRed="always_comb begin\n"
            alwaysRed+=f"\tif(comp_enabled_{node}) begin\n"
            alwaysGreen="always_comb begin\n"
            alwaysGreen+=f"\tif(comp_enabled_{node}) begin\n"
            alwaysBlue="always_comb begin\n"
            alwaysBlue+=f"\tif(comp_enabled_{node}) begin\n"
            alwaysRed+=assignmentsRed
            alwaysGreen+=assignmentsGreen
            alwaysBlue+=assignmentsBlue
            if(len(multRed)==1):
                alwaysRed+=f"\t\top_red = {multRed[0]};\n\tend\n"
                alwaysRed+="\telse begin\n"
                alwaysRed+=f"\t\top_red = 'b0;\n\tend\n"
                alwaysGreen+=f"\t\top_green = {multGreen[0]};\n\tend\n"
                alwaysGreen+="\telse begin\n"
                alwaysGreen+=f"\t\top_green = 'b0;\n\tend\n"
                alwaysBlue+=f"\t\top_blue = {multBlue[0]};\n\tend\n"
                alwaysBlue+="\telse begin\n"
                alwaysBlue+=f"\t\top_blue = 'b0;\n\tend\n"
            else:
                alwaysRed+=f"\t\top_red = {multRed[0]} +\n"
                alwaysGreen+=f"\t\top_green = {multGreen[0]} +\n"
                alwaysBlue+=f"\t\top_blue = {multBlue[0]} +\n"    
                for i in range(1,len(multRed)-1):
                    alwaysRed+=f"\t\t{multRed[i]} +\n"
                    alwaysGreen+=f"\t\t{multGreen[i]} +\n"
                    alwaysBlue+=f"\t\t{multBlue[i]} +\n"
                alwaysRed+=f"\t\t{multRed[-1]};\n\tend\n"
                alwaysRed+="\telse begin\n"
                alwaysRed+=f"\t\top_red = 'b0;\n\tend\n"
                alwaysGreen+=f"\t\t{multGreen[-1]};\n\tend\n"
                alwaysGreen+="\telse begin\n"
                alwaysGreen+=f"\t\top_green = 'b0;\n\tend\n"
                alwaysBlue+=f"\t\t{multBlue[-1]};\n\tend\n"
                alwaysBlue+="\telse begin\n"
                alwaysBlue+=f"\t\top_blue = 'b0;\n\tend\n"
            alwaysRed+="end\n"
            alwaysGreen+="end\n"
            alwaysBlue+="end\n"
            modFile.write(f"\tinput logic comp_enabled_{node},\n")
            computeMods[module].append(f"comp_enabled_{node}")
            modFile.write(f"\toutput logic [CHAN-1:0][BITS-1:0] comp_to_lb_{node}")
            computeMods[module].append(f"comp_to_lb_{node}")
            modFile.write("\n);\n")
            modFile.write(coefs)
            modFile.write(assignments)
            modFile.write(alwaysRed)
            modFile.write(alwaysGreen)
            modFile.write(alwaysBlue)
            modFile.write(f"assign comp_to_lb_{node}[0] = op_red[23:8];")
            modFile.write(f"assign comp_to_lb_{node}[1] = op_green[23:8];")
            modFile.write(f"assign comp_to_lb_{node}[2] = op_blue[23:8];")
            modFile.write("\nendmodule\n\n")
        modFile.close()
        return computeMods


    def genControl(self):
        controlStr=""
        controlStr+="logic [31:0] counter;\n"
        controlStr+="logic [31:0] counterNext;\n"
        alwaysInit="always_ff @(posedge clk or negedge rstn) begin\n"
        alwaysInit+="\tif(!rstn) begin\n"
        alwaysAssign="\telse begin\n"
        for producer in self.stencils.keys():
            oldProducer = producer
            if producer[-2:]=="_1" or producer[-2:]=="_2":
                producer = producer[:-2]
                if producer in self.virtStage.keys() and oldProducer!=self.virtStage[producer][0]:
                    continue
            controlStr+=f"logic write_enabled_{producer};\n"
            alwaysInit+=f"\t\twrite_enabled_{producer} <= 'b0;\n"
            if producer in AST.inputStages:
                alwaysAssign+=f"\t\twrite_enabled_{producer} <= 'b1;\n"
            else:
                alwaysAssign+=f"\t\tif(counter == {int(self.newSCS[oldProducer])}) begin\n"
                alwaysAssign+=f"\t\t\twrite_enabled_{producer} <= 'b1;\n"
                alwaysAssign+=f"\t\tend\n"
            for consumer in self.stencils[oldProducer].keys():
                controlStr+=f"logic read_enabled_{producer}_{consumer};\n"
                alwaysInit+=f"\t\tread_enabled_{producer}_{consumer} <= 'b0;\n"
                alwaysAssign+=f"\t\tif(counter == {int(self.newSCS[consumer]-1-self.stencils[oldProducer][consumer][0])}) begin\n"
                alwaysAssign+=f"\t\t\tread_enabled_{producer}_{consumer} <= 'b1;\n"
                alwaysAssign+="\t\tend\n"
        alwaysInit+="\tend\n"
        alwaysInit+=alwaysAssign
        alwaysInit+="\tend\n"
        alwaysInit+="end\n\n"
        controlStr+="always_ff @(posedge clk or negedge rstn) begin\n"
        controlStr+="\tif (!rstn) begin\n"
        controlStr+="\t\tcounter <= 0;\n"
        controlStr+="\tend\n"
        controlStr+="\telse begin\n"
        controlStr+="\t\tcounter <= counterNext;\n"
        controlStr+="\tend\n"
        controlStr+="end\n"
        controlStr+="assign counterNext = counter+1;\n\n"
        controlStr+=alwaysInit
        return controlStr

    def genCompEnable(self):
        compEnableStr = ""
        compEnableStr+="always_ff @(posedge clk or negedge rstn) begin\n"
        rstnStr = "\tif(!rstn) begin\n"
        enbStr = ""
        for stage in self.newSCS.keys():
            oldStage = stage
            if stage in AST.inputStages:
                continue
            if stage[-2:]=="_1" or stage[-2:]=="_2":
                stage = stage[:-2]
                if oldStage!=self.virtStage[stage][0]:
                    continue
            wire = f"comp_enabled_{stage}"
            self.wires[wire] = ["",""]
            rstnStr+=f"\t\t{wire} <= 'b0;\n"
            enbStr+=f"\t\tif(counter=={self.newSCS[oldStage]-1}) begin\n"
            enbStr+=f"\t\t\t{wire} <= 'b1;\n"
            enbStr+="\t\tend\n"
        rstnStr+="\tend\n\telse begin\n"
        compEnableStr+=rstnStr
        compEnableStr+=enbStr
        compEnableStr+="\tend\nend\n"
        return compEnableStr
        

    def CodeGen(self):
        ramControllerMods,addrGenerators=self.genRAMcontroller()
        fifoMods=self.genFIFO()
        shiftMods=self.genShiftReg()
        computeMods=self.genCompute()
        path=os.path.join(self.OPath,"main.sv")
        modFile=open(path,'a')
        modFile.write("module main_module\n")
        modFile.write("#(\n")
        for param in self.parameters.keys():
            modFile.write(f"\tparameter {param} = {self.parameters[param]},\n")
        modFile.write("\tparameter BITS = 16,\n")
        modFile.write("\tparameter CHAN = 3,\n")
        modFile.write(f"\tparameter WIDTH = {self.width},\n")
        modFile.write(f"\tparameter PORTS = {self.sram}\n")
        modFile.write(")\n")
        modFile.write("(\n")
        modFile.write("\tinput logic clk,\n")
        modFile.write("\tinput logic rstn,\n")
        for i in AST.inputStages:
            modFile.write(f"\tinput logic [47:0] comp_to_lb_{i},\n")
        modFile.write("\toutput logic [47:0] data_out\n")
        modFile.write(");\n\n")
        compEnableStr = self.genCompEnable()
        for wire in self.wires.keys():
            modFile.write(f"logic {self.wires[wire][0]} {wire} {self.wires[wire][1]};\n")
        modFile.write(f"logic [CHAN-1:0][BITS-1:0] comp_to_lb_{AST.outputStage};\n")
        controlStr=self.genControl()
        modFile.write(controlStr)
        # compEnableStr = self.genCompEnable()
        modFile.write(compEnableStr)
        for module in addrGenerators.keys():
            modFile.write(addrGenerators[module])
        for module in ramControllerMods.keys():
            modFile.write(f"{module} {module}_inst\n(\n")
            firstOne=True
            for port in ramControllerMods[module]:
                if(firstOne==False):
                    modFile.write(",\n")
                else:
                    firstOne=False
                modFile.write(f"\t.{port}({port})")
            modFile.write("\n);\n\n")
        for module in shiftMods.keys():
            modFile.write(f"{module} {module}_inst\n(\n")
            firstOne=True
            for port in shiftMods[module]:
                if(firstOne==False):
                    modFile.write(",\n")
                else:
                    firstOne=False
                modFile.write(f"\t.{port}({port})")
            modFile.write("\n);\n\n")
        for module in computeMods.keys():
            modFile.write(f"{module} {module}_inst\n(\n")
            firstOne=True
            for port in computeMods[module]:
                if(firstOne==False):
                    modFile.write(",\n")
                else:
                    firstOne=False
                modFile.write(f"\t.{port}({port})")
            modFile.write("\n);\n\n")
        for module in fifoMods.keys():
            modFile.write(f"{module} {module}_inst\n(\n")
            firstOne=True
            for port in fifoMods[module]:
                if(firstOne==False):
                    modFile.write(",\n")
                else:
                    firstOne=False
                modFile.write(f"\t.{port}({port})")
            modFile.write("\n);\n\n")
        modFile.write(f"assign data_out = comp_to_lb_{AST.outputStage};\n")
        modFile.write("endmodule")
        modFile.close()


def main():
    if(len(sys.argv)<2):
        print("Invalid number of args",end="\n")
        exit()
    elif(len(sys.argv)<3):
        temp=sys.argv[1].strip().split('.')
        temp=temp[0]
        Output=os.getcwd()
        Output=os.path.join(Output,temp)
    else:
        Output=os.getcwd()
        Output=os.path.join(Output,sys.argv[2])
    if(os.path.exists(Output)):
        print(f"The directory that I am going to create {Output} already exists",end='\n')
        print("Do you want to clear its contents? (y/n)")
        ans=input()
        if(ans!='y' and ans!='Y'):
            exit()
        shutil.rmtree(Output)
    os.mkdir(Output)
    Input=sys.argv[1]
    Ifile=open(Input,'r')
    width=480
    sram=2
    sche=schedule(width,sram,Ifile,Output,False)
    # sche=schedule(width,sram,Ifile,Output,True)
    sche.CodeGen()
    shutil.copyfile("controllers/LBController.sv",os.path.join(Output,"LBController.sv"))
    shutil.copyfile("controllers/sramLine.sv",os.path.join(Output,"sramLine.sv"))
    shutil.copyfile("controllers/sram.sv",os.path.join(Output,"sram.sv"))


if __name__=="__main__":
    main()