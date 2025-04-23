# -*- coding: utf-8 -*-

#Addon for EDICO Math Editor
#This file is covered by the GNU General Public License.
#See the file COPYING for more details.
#Copyright (C) 2022 Alberto Zanella - IRIFOR
#Copyright (C) 2023-2025 Alberto Zanella - Edico Targato Italia

import eventHandler
from . import sharedMessages as shMsg
import appModuleHandler
import re
import api
import speech
import textInfos
import NVDAObjects
import config
import addonHandler
import braille
import comHelper
from logHandler import log
import controlTypes
import watchdog
from NVDAObjects.IAccessible import IAccessible

addonHandler.initTranslation()

class EdicoCOMApiProvider :
    _EdicoObjName = 'Edico.EdicoComObj'
    _oEdico = None
    def getApiObject(self) :
        if not self._oEdico : 
            oEdico = comHelper.getActiveObject(self._EdicoObjName,dynamic=True)
            if (oEdico) :
                self._oEdico = oEdico
        return self._oEdico
    
    def isEmpty(self,cnt) : return len(cnt) > 0

edicoApi = EdicoCOMApiProvider()
class EdicoEditor(IAccessible) :
    hasBackspaced = False
    
    CHEM_NUM_COLLECTION = ">,;:*?+=<}"
    CHEM_FONT_NAME = "edico_es_chem"
    
    #Translators: description of the calculator edit box
    CALCULATOR_EQUATION_EDIT = _("equation")
    
    def isInChemMode(self,info) :
        """
        Check if the cursor is positioned in a chemistry-related environment.

        This function analyzes the text formatting at the cursor's location and determines whether it matches the expected chemistry mode font (e.g., for chemical formulas).

        @param info: textInfos.TextInfo : caret-related textInfo

        @return: bool
            - `True` if the cursor is in a chemistry-formatted text field (font matches `self.CHEM_FONT_NAME`).
            - `False` otherwise.
        """
        formatField=textInfos.FormatField()
        for field in info.getTextWithFields(self.appModule.fontFormatConfig):
            if isinstance(field,textInfos.FieldCommand) and isinstance(field.field,textInfos.FormatField):
                formatField.update(field.field)
        return formatField['font-name'] == self.CHEM_FONT_NAME
    
    
    def getChemNum(self,info) :
        """
        Retrieve the proper pronunciation for a subscript digit in chemistry context.

        This function checks if the current cursor position is in chemistry mode and analyzes the preceding characters to determine if they form a valid chemical subscript number.
        If valid, it returns the proper pronunciation for the subscript digit.

        @param info: textInfos.TextInfo
            An object containing text and formatting information at the current cursor position.

        @return: str or None
            - The pronunciation string for the subscript digit if found in chemistry context.
            - None o.w. and if any error occurs during processing
        """
        try :
            if not self.isInChemMode(info) : return None
            chemInfo = info.copy()
            chemInfo.move(textInfos.UNIT_LINE,-1,"start")
            chemTxt = chemInfo.text
            chemTxt = chemTxt[::-1]
            if chemTxt[0] not in self.CHEM_NUM_COLLECTION : return None
            for c in chemTxt[1:] :
                if c in self.CHEM_NUM_COLLECTION :
                    continue
                if c.isalpha() :
                    return str(self.CHEM_NUM_COLLECTION.index(chemTxt[0]))
                else :
                    return None
            return None
        except : return None
    
    def detectPossibleSelectionChange(self) :
        newInfo=self.makeTextInfo(textInfos.POSITION_SELECTION)
        if(len(newInfo.text) == 0) : return
        speech.speakTextSelected(edicoApi.getApiObject().GetHightLightedText())

    def _get_role(self) :
        if(self.IAccessibleObject.accDescription() == self.CALCULATOR_EQUATION_EDIT) :
            return super(EdicoEditor,self)._get_role()
        else: return controlTypes.Role.EDITABLETEXT
    
    def event_gainFocus(self):
        txt = ''
        if self.name :
            txt = txt + self.name
        if(edicoApi.getApiObject().GetObjectTypeAndText(self.windowHandle) != None) :
            txt = txt + edicoApi.getApiObject().GetObjectTypeAndText(self.windowHandle)
        else : txt = txt + edicoApi.getApiObject().GetHightLightedText()
        if edicoApi.getApiObject().GetLine() != None :
            txt = txt + " " + edicoApi.getApiObject().GetLine()
        speech.speakText(txt)
        braille.handler.handleGainFocus(self)
    
    def event_typedCharacter(self, ch):
        if self.hasBackspaced : 
            self.hasBackspaced = False
        else :    
            txt = edicoApi.getApiObject().GetBackSpace()
            if txt == "\u2021" : #Handled by a custom script for Control+J
                pass
            elif config.conf['keyboard']['speakTypedCharacters'] > 0:
                speech.speakText(txt)
        braille.handler.handleCaretMove(self)
    
    #This script is not used, speaks the deleted character instead of the remaining one. This is not the NVDA standard.
    def script_caret_deleteCharacter(self,gesture):
        txt = edicoApi.getApiObject().GetCharacter(9, "Ctrl+J")
        newInfo=self.makeTextInfo(textInfos.POSITION_SELECTION)
        if(len(newInfo.text) == 0) :
            txt = edicoApi.getApiObject().GetChar()
            gesture.send()
        else :
            gesture.send()
            txt = edicoApi.getApiObject().GetChar()
            txt = txt + ", "+ shMsg.GLB_UNSEL
        if config.conf['keyboard']['speakTypedCharacters'] > 0:
            speech.speakText(txt)
        braille.handler.handleCaretMove(self)
    
    def script_caret_backspaceCharacter(self,gesture):
        self.hasBackspaced = True
        txt = edicoApi.getApiObject().GetBackSpace()
        if txt != "\u2021" :
            speech.speakText(txt)
        gesture.send()
    
    def script_reportAddedSymbol(self,gesture):
        gesture.send()
        txt = edicoApi.getApiObject().GetBackSpace()
        speech.speakText(txt)
        braille.handler.handleCaretMove(self)
    
    def script_caret_moveByCharacter(self, gesture):
        gesture.send()
        info = self.makeTextInfo(textInfos.POSITION_SELECTION)
        info.expand(textInfos.UNIT_CHARACTER)
        txt = self.getChemNum(info)
        if not txt : txt = edicoApi.getApiObject().GetChar()
        if( (txt != ' ') and (len(txt) == 1) and re.match("[^A-Za-z0-9]",txt)): 
            speech.speakTextInfo(info, unit=textInfos.UNIT_CHARACTER, reason=controlTypes.OutputReason.CARET)
        else: speech.speakText(txt)
        braille.handler.handleCaretMove(self)
    
    def script_caret_moveByLine(self, gesture):
        gesture.send()
        speech.speakText(edicoApi.getApiObject().GetLine())
        braille.handler.handleCaretMove(self)
    
    def script_caret_moveByWord(self,gesture):
        gesture.send()
        speech.speakText(edicoApi.getApiObject().SayWord())
        braille.handler.handleCaretMove(self)
    
    def script_reportCurrentLine(self,gesture):
        speech.speakText(edicoApi.getApiObject().GetLine())
    #Translators: this is a custom implementation of the globalCommands gesture, it doesn't support spelling.
    script_reportCurrentLine.__doc__=_("Reports the current line under the application cursor.")

    
    def script_reportCurrentSelection(self,gesture):
        speech.speakText(edicoApi.getApiObject().GetHightLightedText())
    #Translators: this is a custom implementation of the globalCommands gesture.
    script_reportCurrentSelection.__doc__=_("Announces the current selection in edit controls and documents.")	

    def script_sayAll(self, gesture):
        speech.speakText(edicoApi.getApiObject().GetAll())
    #Translators: Lambda can't read from the current caret position, the implementation of sayAll provided starts reading from the top of the document.
    script_sayAll.__doc__ = _("reads from the beginning of the document up to the end of the text.")	

    
    def script_f2(self,gesture):
        gesture.send()
        appm = self.appModule
        appm.reportWindowStatus(appm.CONST_BRAILLE_VIEWER_WINDOW)
    
    def script_controlJ(self,gesture):
        txt = edicoApi.getApiObject().GetCharacter(0,"Ctrl+J")
        if config.conf['keyboard']['speakTypedCharacters'] > 0:
            speech.speakText(txt)
        gesture.send()
    
    def script_f4(self,gesture):
        gesture.send()
        appm = self.appModule
        appm.reportWindowStatus(appm.CONST_GRAPHIC_VIEWER_WINDOW)
        
    
    __gestures = {
    'kb:f2': 'f2',
    'kb:control+upArrow': 'caret_moveByLine',
    'kb:control+downArrow': 'caret_moveByLine',
    'kb:control+pageUp': 'caret_moveByLine',
    'kb:control+pageDown': 'caret_moveByLine',
    'kb:control+j': 'controlJ',
    'kb:control+k': 'reportAddedSymbol',
    'kb:control+i': 'reportAddedSymbol',
    'kb:alt+rightArrow': 'caret_moveByCharacter',
    'kb:alt+leftArrow': 'caret_moveByCharacter',
    'kb:alt+1': 'caret_moveByCharacter',
    'kb:alt+2': 'caret_moveByCharacter',
    'kb:alt+3': 'caret_moveByCharacter',
    'kb:alt+4': 'caret_moveByCharacter',
    'kb:control+7': 'reportAddedSymbol',
    'kb:alt+shift+1': 'caret_moveByCharacter',
    'kb:alt+shift+2': 'caret_moveByCharacter',
    'kb:alt+shift+3': 'caret_moveByCharacter',
    'kb:alt+shift+4': 'caret_moveByCharacter',
    'kb:alt+f1': 'caret_moveByCharacter',
    'kb:alt+f2': 'caret_moveByCharacter',
    'kb:alt+f3': 'caret_moveByCharacter',
    'kb:alt+f5': 'caret_moveByCharacter',
    'kb:control+d': 'caret_moveByLine',
    'kb:f4': 'f4',
    "kb:delete": 'caret_moveByCharacter',
    #Report selection
    'kb(desktop):NVDA+shift+upArrow': 'reportCurrentSelection',
    'kb(laptop):NVDA+shift+s': 'reportCurrentSelection',
    #Say Line
    'kb(desktop):NVDA+upArrow': 'reportCurrentLine',
    'kb(laptop):NVDA+l': 'reportCurrentLine',
    #SayAll override
    "kb(desktop):NVDA+downArrow": "sayAll",
    "kb(laptop):NVDA+a": "sayAll",
    }